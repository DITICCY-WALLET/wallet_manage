#!/bin/bash
CRTDIR=$(cd `dirname $0`; pwd)
CONF=$CRTDIR/"gunicorn_conf.py"
APP='run_server'
PORT=20001
GUNICORN_BIN="/root/.virtualenvs/wallet/bin/gunicorn"

$GUNICORN_BIN/gunicorn -b $IP\:$PORT -e PYTHONPATH=$PYTHONPATH:/Volumes/Chocolate/work/projects/wallet/wallet_common -c $CONF $APP\:app -p $PORT

