# Elasticache, Redis clusters and Crossplane

The provisioning of Redis clusters in AWS Elasticache using Crossplane is non-intuitive at various points, but once I got all the parts in place it worked as I wanted. The main goal was to get the basics working so that I could access the cluster endpoint from an EC2 instance running inside the same VPC.

The information/documentation I could find was limited and I ended up changing values key by key, deploying after each change and looking at the results. In many cases it resulted in an error, but this approach got me to where I wanted in the end.



## Crossplane

There are two alternative CRDs ('custom resource definitions') available for Elasticache, *ReplicationGroup* and *CacheCluster*, both of which support Memcache and Redis caching by Elasticache. However, only *ReplicationGroup* returns the Redis endpoint as a Kubernetes secret – this does not appear to have been implemented yet for *CacheCluster*. I have not seen any reason given for this, but it does mean that *ReplicationGroup* is currently the simplest option as getting the endpoint from a *CacheCluster* object would require a Kubernetes Job and some awscli magic.

And at least as far as Elasticache/Redis is concerned, the Crossplane CRD *ReplicationGroup* appears to provide all the provisioning that is needed.


## Elasticache/Redis

### Cluster mode

Reference: [Replication: Redis (Cluster Mode Disabled) vs. Redis (Cluster Mode Enabled)](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/Replication.Redis-RedisCluster.html)

With the correct configurations of parameter group settings and replication group settings, instances with cluster mode enabled and cluster mode disabled can be provisioned. I am not really qualified to describe the difference between the two types, but according to the information from AWS the type of workload will determine which is the better option in a given situation.

For lab and development work, cluster mode disabled is probably better as it can be set up to use a single node. The example manifest for Redis with cluster mode disabled uses the single node configuration.

Cluster mode is set using a value in the parameter group applied to the instance and this setting affects the permissable values of various keys in the manifest for the replication set as some settings are not compatible with one or the other cluster mode setting. Applying a manifest with incompatible values will fail with the error messages shown in the log of the aws provider pod.

### Eviction policy

Reference: [Redis - Key eviction](https://redis.io/docs/manual/eviction/)

*By default, Amazon ElastiCache for Redis sets the* `volatile-lru` *eviction policy for your Redis cluster. When this policy is selected, the least recently used (LRU) keys that have an expiration (TTL) value set are evicted. Other eviction policies are available and can be applied in the configurable* `maxmemory-policy` *parameter.*

The AWS default is unsafe as it requires a TTL value to be set by the application; if this is not the case the cache will fill up and no longer provide caching. This happened in production to an application I was supporting and the solution was to create a new parameter group where the TTL value was ignored, then the least recently accessed keys are evicted once the cache is full regardless of TTL. The other options that are available are described in the reference; the best setting for a given application depends on the workload.

### Security groups

For access within a VPC, an inbound rule with the port for Redis (default 6379) and the CIDR of the is the same as that of the VPC itself is needed. A VPC created by eksctl using the default settings ends up with the CIDR block 192.168.0.0/16 so port range = 6379 and source = 192.168.0.0/16. My example manifest for the security group uses these values.

AWS suggest that a CIDR value of 0.0.0.0/0 (access from anywhere) be used as in this situation as the Elasticache cluster does not have any public IP address in any case, but I find this a little disturbing.

I haven’t tested access from outside of the VPC; information about this is provided by AWS:

[Access Patterns for Accessing an ElastiCache Cluster in an Amazon VPC](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/elasticache-vpc-accessing.html)

## Redis client for testing access

There is a command line Redis client that can be used for various things, including testing access. A simple one-liner to install the client on an EC2 instance is:

`sudo amazon-linux-extras install epel -y && sudo yum update -y && sudo yum install redis -y`

To check that it has been installed

`redis-cli -v`

To verify access, deploy an EC2 instance in the same VPC (the example security group allows access from with the same VPC), install the Redis client as above and run the following command using the redis endpoint that is saved in the Kubernetes secret defined by the value of writeConnectionSecretToRef: in the manifest file.

`redis-cli -h <endpoint> ping`

`redis-cli -h redis-cluster-mode-off.8ym5s5.ng.0001.eun1.cache.amazonaws.com ping`

To verify access in a non-production environment, the quickest is just to start a terminal session on one of the EKS nodes using the AWS SSM Fleet manager, install the Redis cli client as above and check access.

## Putting it together

The examples below have been deployed both in the same VPC that the EKS cluster that I have Crossplane on (the VPC + EKS cluster were created using eksctl and Crossplane deployed using Helm) was running on and in the default VPC for the AWS region. The components not deployed using Crossplane needed to be referenced using their AWS IDs; other components could be referenced by name. Don't regard my formatting and configuration as the only correct way of doing this; use whatever works for you.

### Components/Steps

1. Parameter group, with cluster mode set either off or on
2. VPC and subnets
3. Security group allowing access to the Redis port from within the VPC
4. Redis subnet group, defined to use subnets within the VPC
5. Redis instance, configured according to whether cluster mode is on or off

### Provisioning

Some components are prerequisites to other components so order of deployment is important.

- Step 1 can be provisioned at any point before step 5
- Step 2 provisioning the VPC and associated subnets must be done before steps 3 and 4
- Steps 3 and 4 can be done in any order between the steps 2 and 5
- Step 5 is the final step

### Example Crossplane manifests

The VPC and subnets are taken as given, mainly because I didn't use Crossplane to deploy them for my test environment but anybody using the information given in this document will most likely know multiple ways or provisioning VPCs in any case.

These are basically the manifest files I ended up with once I'd got provisioning to work the way I wanted; they have been cleaned up a little and verified. They most will need editing to work in another environment, even if you use the same AWS region as I did (`eu-north-1`).

There are too many lines to include all the manifests in this markdown document so the manifest files are distributed separately and linked to from this document.

#### 1 Manifest files to provision Parameter groups

[Parameter group with cluster mode turned off and safe eviction](/elasticache-redis/clustermodeoff_parametergroup.yaml)

[Parameter group with cluster mode turned on and safe eviction](/elasticache-redis/clustermodeon_parametergroup.yaml)

#### 2 VPC

You fix this yourself

#### 3 Security group

Requires a VPC; needs updating with that VPC's identity

[Security group for both cluster nodes](/elasticache-redis/securitygroup.yaml)

#### 4 Elasticache subnet group

Requires subnets in the VPC from previous step and updating with the subnet details

[Subnet group for both cluster modes](/elasticache-redis/subnetgroup.yaml)

#### 5 Elasticache/Redis instances

Both use t3.micro nodes; one node where cluster mode is disabled and two for the other

[Redis instance with cluster mode disabled](/elasticache-redis/clustermodeoff_replicationgroup.yaml)

Endpoint for the above instance is in the secret `redis-clustermode-off` in the namespace `crossplane-system`

[Redis instance with cluster mode enabled](/elasticache-redis/clustermodeon_replicationgroup.yaml)

And for this instance in the secret redis-clustermode-on` in the namespace `crossplane-system`


