FROM python:3.7.2-stretch

RUN pip install kubernetes redis

COPY ./redis-labeler.py .

ENTRYPOINT [ "python3" ]

CMD ["./redis-labeler.py"]
