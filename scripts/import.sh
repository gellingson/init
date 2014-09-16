#!/bin/bash

# if we don't already have vars set, try to set them
if [ -z $OGL_LOGDIR ] ; then . /home/ubuntu/.profile ; fi
if [ -z $OGL_LOGDIR ] ; then exit ; fi

LOGFILE=$OGL_LOGDIR/importlog
echo `/bin/date` "Running an import [args $@] with output to $LOGFILE" >> /home/ubuntu/logfile_name
echo '=====' `/bin/date` 'Key environment' >> $LOGFILE
echo "USER=$USER" >> $LOGFILE
echo "OGL_STAGE=$OGL_STAGE" >> $LOGFILE
echo "OGL_PYTHON=$OGL_PYTHON" >> $LOGFILE
echo "PYTHONPATH=$PYTHONPATH" >> $LOGFILE
echo '=====' `/bin/date` "Starting importer.py with args $@" >> $LOGFILE
$OGL_PYTHON $OGL_STAGE/inventory/importer.py $@ &>> $LOGFILE
echo '=====' `/bin/date` 'Finished importer.py' >> $LOGFILE

