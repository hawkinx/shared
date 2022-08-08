# S3 buckets, object lifecycling and Crossplane

#### S3 is not just object storage, it includes fairly sophisticated storage lifecycling functions to manage data transition between storage classes

There are multiple storage classes available, ranging from standard S3 with the highest cost, through various classes with combinations of less frequent access, longer latency and retrieval times, and single zone storage, optimised for various use cases. AWS sometimes describe this in terms of 'hot' versus 'cold' storage. Common use cases would be *S3 One Zone* single zone storage for high volume non-critical data and *S3 Glacier Deep Archive* for data required to be archived for compliance reasons but typically never accessed again - with a retrieval time measured in hours it is probably not suitable for disaster recovery. Expiration and deletion of objects can also be managed as part of storage lifecycling.

There is also an option - *S3 Intelligent-Tiering* - where for a monthly fee objects that have not been accessed after predefined time intervals are moved to lower cost storage tiers. If accessed, objects are returned to the standard storage tier where the countdown restarts.

### Table of available S3 storage classes

|                                    | S3 Standard            | S3 Intelligent-Tiering | S3 Standard-IA         | S3 One Zone-IA         | S3 Glacier Instant Retrieval | S3 Glacier Flexible Retrieval | S3 Glacier Deep Archive |
|:---------------------------------- |:---------------------- | ---------------------- | ---------------------- | ---------------------- | ---------------------------- | ----------------------------- |:----------------------- |
| Designed for durability            | 99.999999999% (11 9’s) | 99.999999999% (11 9’s) | 99.999999999% (11 9’s) | 99.999999999% (11 9’s) | 99.999999999% (11 9’s)       | 99.999999999% (11 9’s)        | 99.999999999% (11 9’s)  |
| Designed for availability          | 99.99%                 | 99.9%                  | 99.9%                  | 99.5%                  | 99.9%                        | 99.99%                        | 99.99%                  |
| Availability SLA                   | 99.9%                  | 99%                    | 99%                    | 99%                    | 99%                          | 99.%                          | 99.9%                   |
| Availability Zones                 | ≥3                     | ≥3                     | ≥3                     | 1                      | ≥3                           | ≥3                            | ≥3                      |
| Minimum capacity charge per object | N/A                    | N/A                    | 128 KB                 | 128 KB                 | 128 KB                       | 40 KB                         | 40 KB                   |
| Minimum storage duration charge    | N/A                    | N/A                    | 30 days                | 30 days                | 90 days                      | 90 days                       | 180 days                |
| Retrieval charge                   | N/A                    | N/A                    | per GB retrieved       | per GB retrieved       | per GB retrieved             | per GB retrieved              | per GB retrieved        |
| First byte latency                 | milliseconds           | milliseconds           | milliseconds           | milliseconds           | milliseconds                 | minutes or hours              | hours                   |
| Storage type                       | Object                 | Object                 | Object                 | Object                 | Object                       | Object                        | Object                  |
| Storage type                       | Object                 | Object                 | Object                 | Object                 | Object                       | Object                        | Object                  |

Note that a small monthly fee is charged for *Intelligent Tiering* to cover analysis resource usage. 

Storage charges per GB vary by a factor of a little over 20 from the lowest to highest storage cost, with the proviso that retrieval from lower cost tiers is charged for.

Detailed information on S3 pricing per region can be found on this page: [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/)

Storage class transitioning is subject to a number of constraints, mainly related to the minimum number of days required for objects to be stored in the low access classes, but also related to the size of the objects.

S3 pricing is a little complicated given the number of tiers available and that data transfer charges apply for some scenarios such as retrieving data from S3 or transferring it between regions, but for normal business use the cost of S3 data storage is generally insignificant compared with the costs for other AWS services. Legal issues relating to archive retention requirements, data localisation and the handling of personally identifiable information (PII) are likely to be more important.

A suggested approach when designing a strategy for S3 storage lifecycling is to begin by identifying and categorising classes of data with differing lifecycle requirements. These can then be mapped to S3 data lifecycling, perhaps with some iteration of the categorisation process in order to get a better fit between requirements and S3 options.

## Management of S3 lifecycling with Crossplane

References:

[Crossplane - Bucket.v1beta1.s3.aws.crossplane.io](https://doc.crds.dev/github.com/crossplane/provider-aws/s3.aws.crossplane.io/Bucket/v1beta1@v0.29.0)

[AWS - Managing your storage lifecycle](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)

The Crossplane AWS Provider object `Bucket.v1beta1.s3.aws.crossplane.io` doesn't support all of the S3 lifecycling settings; there are probably good reasons for this, but the most important thing in practice is to be aware that this is the case when when looking at AWS’ own API documentation and to verify any setting before deciding to use it. Nothing important appears to be missing however so it is unlikely to be an issue.

Example manifest file for a lifecycle configuration proof-of-concept bucket; the rules included in the example are there for illustration rather than to make sense.

```
# Proof-of-concept/demo manifest file for Crossplane AWS S3
# Can be verified using the command
#   aws s3api get-bucket-lifecycle-configuration --bucket bucket-name-that-is-globally-unique
---
apiVersion: s3.aws.crossplane.io/v1beta1
kind: Bucket
metadata:
  name: testbucket
  namespace: default
  annotations:
    crossplane.io/external-name: bucket-name-that-is-globally-unique
spec:
  deletionPolicy: Delete
  forProvider:
    acl: private
    locationConstraint: eu-north-1
    publicAccessBlockConfiguration:
      blockPublicPolicy: true
    lifecycleConfiguration:
      rules:
        # A rule with multiple settings
        - status: Enabled
          id: rule_with_multiple_settings
          filter:
            prefix: "xiferp/"
          abortIncompleteMultipartUpload:
            daysAfterInitiation: 15
          expiration:
            days: 366
          noncurrentVersionExpiration:
            noncurrentDays: 63
        # Rule with single setting
        - status: Enabled
          id: rule_with_one_setting
          transitions:
            - days: 95
              storageClass: "INTELLIGENT_TIERING"
  providerConfigRef:
    name: provider-aws
```

## S3 buckets, lifecycling and replication

While replication might not seem belong to data lifecycling, it is appropriate to mention it in this context as there are use cases that combine lifecycling and replication.

Reference: [AWS S3 Replicating objects](https://docs.aws.amazon.com/AmazonS3/latest/userguide/replication.html)

The AWS documentation suggests possible reasons for replication might be legal or compliance requirements for storage of data at multiple geographical sites or in multiple AWS accounts (objects can be replicated automatically to different storage classes in buckets in different accounts as well as in different regions) and lifecycled to lower cost storage classes. A more practical reason might be for cross-regional disaster recovery, where data is replicated to a secondary region in near real-time then removed a short time later using lifecycling rules to limit costs related to storing multiple copies of data unnecessarily. 

#### Replication and Crossplane

Replication configuration can be managed by Crossplane. No proof-of-concept has been carried out, but the example manifest file for buckets contains a good example of how to configure replication, including how to set up and reference a target bucket. 

[Crossplane example manifest for S3 buckets](https://github.com/crossplane-contrib/provider-aws/blob/master/examples/s3/bucket.yaml)
