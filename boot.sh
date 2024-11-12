#!/bin/bash

#kill db connection attempts after 1min, just in case
MAX_ATTEMPTS=12
attempt=1

while [ $attempt -le $MAX_ATTEMPTS ]; do
    flask db upgrade
    if [[ "$?" == "0" ]]; then
        break
    fi
    if [[ $attempt -eq $MAX_ATTEMPTS ]]; then
    	echo "Upgrade command failed on attempt #$attempt, this is the last attempt to start the DB. 
    	Something is wrong with DB initialization, please check your setup and try again."
    else
    	echo "Upgrade command failed on attempt #$attempt, retrying in 5 secs..."
    	attempt=$((attempt+1))
    fi
    sleep 5
done
exec gunicorn -b :5000 --access-logfile - --error-logfile - ai_companion:app