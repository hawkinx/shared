
FROM python:3.11-slim-bullseye

WORKDIR /app

# Ignore the warning about running pip as root; not relevant here. Works from pip 22.1
ENV PIP_ROOT_USER_ACTION=ignore
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

CMD ["python", "take_snapshots.py"]
