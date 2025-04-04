FROM python:3.12

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
RUN pip install pymysql cryptography

COPY app app
COPY migrations migrations
COPY ai_companion.py config.py boot.sh ./
RUN chmod a+x boot.sh

ENV FLASK_APP=ai_companion.py
# A temporary DEBUG variable to allow logging without any significant app changes. Will remove and adjust this later.
ENV FLASK_DEBUG=1
# We haven't set up translation services yet
# RUN flask translate compile

RUN apt-get update && apt-get install -y nmap vim

EXPOSE 5000
ENTRYPOINT ["./boot.sh"]