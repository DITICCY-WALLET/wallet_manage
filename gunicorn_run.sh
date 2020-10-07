#!/bin/bash
CONF='gunicorn_conf.py'
APP='run_server'
PORT=20001

gunicorn -b $IP\:$PORT -e PYTHONPATH=$PYTHONPATH:/Volumes/Chocolate/work/projects/wallet/wallet_common -c $CONF $APP\:app -p $PORT

