FROM hysds/pge-gdal:latest

MAINTAINER jlinick "Justin.P.Linick@jpl.nasa.gov"
LABEL description="PGE for AOI creation"

USER ops
COPY . /home/ops/verdi/ops/create_aoi

# install browse generation package
#RUN git clone --depth=1 https://${GIT_OAUTH_TOKEN}@github.jpl.nasa.gov/aria-hysds/generate_browse_imagery.git ${HOME}/verdi/ops/generate_browse_imagery
#RUN sudo python ${HOME}/verdi/ops/generate_browse_imagery/setup.py install

# set entrypoint
WORKDIR /home/ops
CMD ["/bin/bash", "--login"]
