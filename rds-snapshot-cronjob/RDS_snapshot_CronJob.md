# Simple solution for RDS snapshots

### Background

RDS snapshots are EBS based snapshots of RDS instances. An individual snapshot will include all changes in the database instance since the previous snapshot, but because of the way they are integrated with EBS storage, each snapshot is also a copy of the entire database instance. Copying a single snapshot to for example an S3 bucket will result in a complete copy of that database instance being copied, not just the changes included in that specific snapshot. Another way of illustrating this is that if all snapshots but the latest are deleted, that snapshot will still be a full copy of the RDS instance at the point in time when the snapshot was taken. As such, they are not the same as old-style incremental backups and should not be confused with them.

The default automated AWS snapshot solution is a bit restricted – you are limited to one snapshot per 24 hours with a maximum retention time of 35 days. If this does not fulfill requirements, so called ‘manual snapshots’ can be used instead. In this situation it is probably best to disable automatic snapshots altogether by setting retention time to 0 days, to save on storage.

### Python scripts and manual snapshots

Using Python and the boto3 library it is fairly straight forward to deal with snapshot management. In the past I have done this using Lambda scripts, but handing maintenance of these over to colleagues when I left that particular project turned out to be a bit of an problem. They had better AWS certifications that I had, but presumably due to a lack of coding experience their eyes basically just glazed over when we went through code and documentation. There is less Python code involved with the CronJobs in this solution and the script structure is much more similar to that of shell scripts, so should be easier to understand for sysadmins in general.

Keeping things simple and deploying the scripts as Kubernetes CronJobs results in simpler code plus it better fits with the Kubernetes/EKS based platform we are working on. If we were spinning up hundreds or thousands of instances at a time Lambda would be better performance wise, but for simple housekeeping scripts CronJobs are good enough.

### Simple Boto3/Python/Kubernetes/CronJob solution

It consists of two scripts and in its current form runs within a single AWS account, managing snapshots for all RDS instances in that account. As the project I have built this for is only using PostgreSQL database instances it has been developed and tested with these only. The Lambda script solutions I worked with in the past were also written in Python, doing much the same thing with MariaDB and MySQL instances (all scheduling was hardcoded though in this case, which simplified things).

The first script gets a list of all RDS instances and steps through the list, taking snapshots according to whatever schedule has been defined for each RDS instance. I've designed the script to be run on an hourly basis so logging and what error handling there is, is managed by the hour. It only picks up RDS instances in the AWS account that it is running in so will need to be deployed in every account.

The second script steps through all manual snapshots and deletes any that are older than an expiry timestamp that in turn was calculated by the first script from a defined retention period and attached to the snapshot. This script can be run at any time, independently of the first script.

There are a number of possible improvements; some are mentioned in this documentation, most are not. The solution does what it needs to do already so is good enough for now.

#### Defining schedules

Scheduling and retention time are defined per RDS instance using AWS tags; if none are defined, default values of once per day just after 0200 UTC and 90 day retention are hard coded in the script taking the snapshots. Snapshots can be disabled by setting a tag also; this means that an active decision not to take any backups has to be made. Using AWS tags has some limitations due to the characters that are available, but it is simple to set up for individual database instances. If different default values are desired, the Python script can be updated. A future addition to the script for the future would be to enable input the default values as environmental variables.

#### Tags
`snapshot_retention_days`  
Number of days to retain the snapshot; used to calculate value in snapshot expiry tag    
E.g. `35`, default `90`

`snapshot_schedule`  
Space separated list of whole hours 00 - 23 to take snapshots (must be '00' '01' not '0' '1' etc)  
E.g. `00 08 16`, default `02`

`snapshot_latest`  
Tracks successful snapshots; content is either the hour of the successful snapshot or 'skipped' if not (mainly occurs when the database is not in a non-available state where snapshots are possible).  
Set by script

`snapshot_never`  
Disables snapshots if it exists; tag content is ignored as are all other tags so can be used to disable snapshots temporarily without deleting other tags

`snapshot_expiry`  
Attached to each individual snapshot and read by the script that cleans up snapshots; created by the script and can be deleted to disable the clean-up script for a specific snapshot  
Set by script


#### Packaging the scripts into container images

For these scripts to be useful they need to be run regularly, which means that container images with the scripts are built and deployed.

The two scripts are packaged and deployed separately in this current solution; it might not be the most optimal long term, but it gets the job done and is good enough for now.

In the [subdirectory](take_snapshots) for script that takes the snapshots:

```
cronjob.yaml
Dockerfile
.dockerignore
requirements.txt
take_snapshots.py
```
For the second [script], the file `take_snapshots.py` is replaced by `delete_snapshots.py` in the [subdirectory](delete_snapshots).

`Dockerfile` contains the information to build the container image and `.dockerignore` which files should be ignored by the container build process. The file `requirements.txt` was generated from inside a Python virtual environment and lists various dependencies of the script. I have not included the virtual environment files in the code repository as there are about 100 Mbyte of files. `.dockerignore` includes the line `.venv` to exclude these files if you set the virtual environment up locally.

The sequence of commands to create the virtual environment, download the dependencies and create the `requirements.txt` file are:

```
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install boto3 datetime
python3 -m pip freeze > requirements.txt
```

`boto3` is the AWS Python library and `datetime` is a standard Python library. 

The container image that I use as a base is Amazon's latest image for *Amazon Linux 2* [amazonlinux/amazonlinux](https://gallery.ecr.aws/amazonlinux/amazonlinux). It is quite a bit (3x) larger than the official Python image, but the ECR vulnerability scan warns about one high level vulnerability and a number of lower level vulnerabilities for the Python image while the image built using Amazon Linux shows none. 

Build and tag the image using the regular `docker build` command

Once the images are built they need to be checked in to a container repository; for now I have checked them into my personal Dockerhub account and the manifest files for the CronJobs pull the images from there, but AWS' own repository ECR is probably the best place for them.

### Deploying the images as Kubernetes CronJobs

Manifest files – `cronjob.yaml` – are included in both of the script subdirectories. These are fairly straightforward to understand and to use. The container image details will need updating once you start creating your own images (I don’t recommend using mine except maybe for proof-of-concept)

Both cronjob definitions use the same service account, which I have named 'cronjob-rds-snapshot'. This service account needs to be set up according to the irsa (IAM Roles for Service Accounts) model. The way service accounts are set up will likely depend on the way your deployment is managed, but for my development and test work I used the `eksctl` command line tool ([https://eksctl.io/](https://eksctl.io/)) and the regular `aws` cli tool ([https://aws.amazon.com/cli/](https://aws.amazon.com/cli/))

The EKS cluster needs to have an OIDC identity provider set up then two things need to be done – define an IAM policy with the necessary rights and create the irsa.

I always define my lab EKS clusters with OIDC enabled so that irsa accounts can be used. The following awscli command can be used to check if an EKS cluster has OIDC configured correctly:

```
aws eks describe-cluster --name cluster_name \
  --query cluster.identity.oidc.issuer --output text
```

‘cluster_name’ is the name of the cluster being queried and region needs to be specified if it’s in another region than your default awscli region.

Something like the following will be returned:
```
https://oidc.eks.eu-north-1.amazonaws.com/id/567890ABCDF123457890ABDEF12456
```

Now define an IAM policy with the necessary rights

The file `snapshotpolicy.json` is included with the documentation in the sub-directory [irsa](irsa); it allows the service account to read information about database instances and snapshots as well as create and delete snapshots and tags. 

To create the policy using awscli:
```
aws iam create-policy --policy-name rds-snapshot-policy \
  --policy-document file://snapshotpolicy.json
```

The policy name is set to 'rds-snapshot-policy' here; change it by all means but you’ll need to be sure that the new name is used in all subsequent commands also

An ARN is returned that if the command is successful; this is needed when creating the service account. Something like the following is returned:

```
arn:aws:iam::012345678901:policy/rds-snapshot-policy
```

The last step is to create the irsa service account using the eksctl tool. 

Once again the 'cluster_name' value needs to be changed to whatever is being used. The ARN string for the IAM policy will need updating also as it includes the account name.

```
eksctl create iamserviceaccount --cluster=cluster_name \
  --name=cronjob-rds-snapshot \
  --attach-policy-arn=arn:aws:iam::012345678901:policy/rds-snapshot-policy \
  --override-existing-serviceaccounts --approve
```

Finally deploy the two cronjobs using the manifest files 

### S3 for extra security

Snapshots are stored on EBS block storage, which is not as reliable as S3 distributed object storage so some sort of regular export of snapshots to S3 is recommended, particularly for business critical data. This could either be added to one of the existing scripts with some more Python code or run as a separate script and CronJob. 

The target S3 bucket can be in another AWS account and/or in another AWS region. To protect the snapshots against removal by malicious actors or just deletion in general, S3 bucket Object Lock can be in addition enabled. This provides the same protection as an AWS Backup Vault Lock, but without having to set up a Backup Vault.

