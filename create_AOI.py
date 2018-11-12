#!/usr/bin/env python

'''
Simple AOI generation script
'''

import os
import re
import ast
import json
import shutil
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import socket
import getpass
import dateutil.parser
from shapely.geometry import Polygon, mapping
from hysds_commons.net_utils import get_container_host_ip

def main():
    '''generates the aoi dataset and met from context.json'''
    context = load_json('_context.json') #load your context file as a dict
    # load your basic configs for met & dataset
    ds = load_json(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'config/AOI.dataset.json'))
    met = load_json(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'config/AOI.met.json'))
    # build input ds & met from context variables
    ds = build_aoi_ds(context, ds)
    met = build_aoi_met(context, met)
    # save as a HySDS product
    save_files(ds, met)
    return ds, met

def build_aoi_ds(context, ds):
    '''generates the aoi dataset json from the context inputs'''
    aoi_type = validate_type(context['type'])
    label = generate_label(context['name'], aoi_type)
    project = context['account']
    polygon_geojson = validate_geojson(context['geojson_polygon'])
    starttime = validate_time(context['starttime'])
    endtime = validate_time(context['endtime'])
    if 'emails' in context.keys():
        email_list = ds['emails']
        additional_emails = parse_emails(context['emails'])
        email_list = list(set(email_list + additional_emails))
    #save to ds object
    ds['label'] = label
    ds['type'] = aoi_type
    ds['account'] = project
    ds['location'] = polygon_geojson
    ds['starttime'] = starttime
    ds['endtime'] = endtime
    ds['emails'] = email_list
    return ds

def build_aoi_met(context, met):
    '''build the aoi met dict'''
    if 'username' in context.keys():
        met['username'] = context['username']
    if 'eventtime' in context.keys():
        event_time = validate_event_time(context['eventtime'])
        if event_time != None:
            met['eventtime'] = event_time
    if 'image_url' in context.keys():
        met['image_url'] = context['image_url']
    if 'additional_metadata' in context.keys():
        met = parse_additional_metadata(context['additional_metadata'], met)
    return met

def parse_additional_metadata(additional_met, met):
    '''parse out additional metadata from context and append it properly to met dict'''
    if additional_met == '' or additional_met is None:
        return met
    if type(additional_met) is not dict:
        try:
            additional_met = json.loads(additional_met)
        except:
            try:
                additional_met = ast.literal_eval(additional_met)
            except:
                raise Exception('additional metadata cannot be parsed')
    #additional_metadata is a dict
    if 'user' in additional_met.keys():
        met['username'] = additional_met['username']
    if 'eventtime' in additional_met.keys():
        event_time = validate_event_time(additional_met['eventtime'])
        if event_time != None:
            met['eventtime'] = event_time
    if 'image_url' in additional_met.keys():
        met['image_url'] = additional_met['image_url']
    if 'event_metadata' in additional_met.keys():
        met['event_metadata'] = additional_met['event_metadata']
    return met

def generate_label(label, aoi_type):
    '''validates the aoi name, appending an AOI_ if necessary'''
    label = re.sub(r"[^a-zA-Z0-9_]+", '', label.replace(' ', '_'))
    if label.startswith('AOI_'):
        label = label.lstrip('AOI_')
    return 'AOI_{0}_{1}'.format(aoi_type, label)

def validate_type(aoi_type):
    '''simply strips non-chars/ints & replaces spaces with underscore'''
    return  re.sub(r"[^a-zA-Z0-9_]+", '', aoi_type.replace(' ', '_'))

def validate_time(input_time_string):
    '''parses the input time string and ensures it's the proper format'''
    try:
        outtime = dateutil.parser.parse(input_time_string)
        out_string = outtime.strftime('%Y-%m-%dT%H:%M:%SZ')
    except:
        raise Exception('unable to parse input time: {0}'.format(input_time_string))
    return out_string

def validate_event_time(input_time_string):
    '''parses the input time string and ensures it's the proper format'''
    if input_time_string == '':
        return None
    try:
        outtime = dateutil.parser.parse(input_time_string)
        out_string = outtime.strftime('%Y-%m-%dT%H:%M:%SZ')
    except:
        raise Exception('unable to parse input time: {0}'.format(input_time_string))
    return out_string

def validate_geojson(input_geojson):
    '''validates the input geojson into a full geojson polygon object'''
    if type(input_geojson) is str:
        try:
            input_geojson = json.loads(input_geojson)
        except:
            try:
                input_geojson = ast.literal_eval(input_geojson)
            except:
                raise Exception('unable to parse input geojson string: {0}'.format(input_geojson))
    #attempt to parse the coordinates to ensure a valid geojson
    try:
        # if it's a full geojson
        if 'coordinates' in input_geojson.keys():
            polygon = Polygon(input_geojson['coordinates'][0])
            location = mapping(polygon)
            return location
        else: # it's a list of coordinates
            polygon = Polygon(input_geojson)
            location = mapping(polygon)
            return location
    except:
        raise Exception('unable to parse geojson: {0}'.format(input_geojson))

def parse_emails(emails):
    '''parse the input emails and return them as a list (input can be string or list'''
    if isinstance(emails, (list,)):
        return [validate_email(item) for item in emails]
    email_list = emails.split(',')
    return [validate_email(item) for item in email_list]

def validate_email(email):
    '''not really validating as email, just removing spaces so the email client doesnt die'''
    return email.replace(' ', '')

def load_json(file_path):
    '''load the file path into a dict and return the dict'''
    with open(file_path, 'r') as json_data:
        json_dict = json.load(json_data)
        json_data.close()
    return json_dict

def download_browse(url, directory):
    '''downloads the browse file as browse.png, just continues if it fails'''
    try:
        import osaka.main
        osaka.main.get(url, directory)
        filename = os.path.basename(url)
        fn_path = os.path.join(directory, filename)
        browse_path = os.path.join(directory, 'browse.png')
        browse_small_path = os.path.join(directory, 'browse_small.png')
        shutil.move(fn_path, browse_path)
        shutil.copy2(browse_path, browse_small_path)
    except:
        pass

def save_files(ds, met):
    '''save the dataset and met files properly'''
    label = ds['label']
    if not os.path.exists(label):
        os.mkdir(label)
    ds_path = os.path.join(label, '{0}.dataset.json'.format(label))
    met_path = os.path.join(label, '{0}.met.json'.format(label))
    #stick label from event_metadata in the field if it exists
    try:
        ds['label'] = met['event_metadata']['label']
    except:
        pass
    with open(ds_path, 'w') as outf:
        json.dump(ds, outf)
    with open(met_path, 'w') as outf:
        json.dump(met, outf)
    #save the browse image if it exists
    if 'image_url' in met.keys():
        image_url = met['image_url']
        download_browse(image_url, label)
    else:
        #generate the browse using our package
        try:
            import generate_browse_imagery #lazy import
            browse_base_path = os.path.join(label, label)
            coords = list(ds['location']['coordinates'])
            coords = [list(item) for item in coords]
            geojson_obj = {"type": "Polygon", "coordinates": coords}
            #print('geojson obj: {}'.format(geojson_obj))
            #generate browse imagery
            generate_browse_imagery.generate(geojson_obj, browse_base_path)
            #copy browse to browse small
            if os.path.exists(browse_base_path + '.browse.png'):
                shutil.copy2( browse_base_path + '.browse.png', browse_base_path + '.browse_small.png')
            #generate kml for leaflet
            generate_kml(browse_base_path)
            met['tiles'] = True
            #rewrite met
            with open(met_path, 'w') as outf:
                json.dump(met, outf)
        except:
            pass

def generate_kml(base_path):
    '''runs gdal2tiles using the input geojson'''
    input_file = base_path + '.geo.tif'
    if not os.path.exists(input_file):
        return False
    tiles_dir = os.path.join(os.path.dirname(input_file), 'tiles')
    if not os.path.exists(tiles_dir):
        os.mkdir(tiles_dir)
    output_dir = os.path.join(os.path.dirname(input_file), 'tiles', 'extent')
    gdal_cmd = 'gdal2tiles.py -p mercator {} -z 2-8 -k {}'.format(input_file, output_dir)
    os.system(gdal_cmd)

def send_fail_email(error):
    '''sends email marking failure of aoi creation'''
    error = str(error).strip('"')
    context = load_json('_context.json')
    emails = []
    if 'emails' in context.keys():
        emails = parse_emails(context['emails'])
    ds = load_json(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'config/AOI.dataset.json'))
    if 'emails' in ds.keys():
        emails = emails + parse_emails(ds['emails'])
    emails = list(set(emails))
    now = str(datetime.now())
    name = context['name']
    job_json = load_json('_job.json')
    job_id = job_json['job_id']
    task_id = job_json['task_id']
    current_dir = os.path.dirname(os.path.realpath(__file__))
    current_dir = os.path.dirname(os.path.realpath(__file__))
    email_config = os.path.join(current_dir, 'config', 'failure_email.txt')
    with open(email_config, 'r') as infile:
        body = infile.read()
    user = ''
    if 'username' in context.keys():
        user = context['username']
    body = body.format(now, name, job_id, task_id,  error, user)
    subject = 'Failed: Create AOI {0}'.format(name)
    send_email(emails, subject, body)
        
def send_success_email(ds, met):
    '''sends an email marking success of aoi creation'''
    current_dir = os.path.dirname(os.path.realpath(__file__))
    email_config = os.path.join(current_dir, 'config', 'success_email.txt')
    with open(email_config, 'r') as infile:
        body = infile.read()
    name = ds['label']
    aoi_type = ds['type']
    now = str(datetime.now())
    starttime = ds['starttime']
    eventtime = 'None'
    if 'eventtime' in met.keys():
        eventtime = met['eventtime']
    endtime = ds['endtime']
    coordinates = json.dumps(ds['location']['coordinates'])
    user = ''
    if 'username' in met.keys():
        user = met['username']
    emails = ds['emails']
    subject = 'Completed: Create AOI {0}'.format(name)
    body = body.format(name, aoi_type, starttime, eventtime, endtime, coordinates, now, user)
    send_email(emails, subject, body)

def send_email(send_to, subject, body):
    '''send email with given inputs'''
    send_to = [str(email) for email in send_to]
    msg = MIMEText(body)
    send_to_str = ', '.join(send_to)
    #sender = '{0}@{1}'.format(getpass.getuser(), get_hostname())
    sender = 'aria-ops@jpl.nasa.gov'
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = send_to_str
    print('Sending email.\nFrom: {0}\nTo: {1}\nSubject:: {2}\nBody: {3}'.format(sender, send_to, subject,  body))
    smtp_obj = smtplib.SMTP(get_container_host_ip())
    smtp_obj.sendmail(sender, send_to, msg.as_string())
    smtp_obj.quit()

def get_hostname():
    '''Get hostname.'''
    try: return socket.getfqdn()
    except:
        try: return socket.gethostbyname(socket.gethostname())
        except:
            raise RuntimeError("Failed to resolve hostname for full email address. Check system.")


if __name__ == '__main__':
    #try:
    ds, met = main() # parse info from context and save as HySDS AOI product
    #except Exception, e:
    #    send_fail_email(e) #send emails on failure & exit
    #    raise Exception(e)
    #send_success_email(ds, met)

