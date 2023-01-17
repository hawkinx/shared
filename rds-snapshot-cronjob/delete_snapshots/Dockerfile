# Use the latest Amazon 2 image as the base 
# 3x larger than the official Python images but clean according to ECR vulnerability scanning
FROM public.ecr.aws/amazonlinux/amazonlinux:2

WORKDIR /app

# Ignore the warning about running pip as root; not relevant here. Works from pip 22.1
ENV PIP_ROOT_USER_ACTION=ignore

# Install python 3.8 and set it to default for both python and python3
RUN amazon-linux-extras enable python3.8
RUN yum install python3.8 -y
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.8 1
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.8 1

# Install dependencies
COPY requirements.txt requirements.txt
RUN python3 -m pip install -r requirements.txt

COPY . .

CMD ["python", "delete_snapshots.py"]
