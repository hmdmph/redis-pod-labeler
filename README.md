# mongo-pod-labeler
Docker image for find and label the mongo pods in the kubernetes cluster according to the role ( primary, secondary) 

[Docker Image Link](https://hub.docker.com/r/redmart/mongo-pod-labeler)

## Description
A simple python script to find the mongo pods in Kubernetes for the given labels and label them according to the rule.
mongo command `isMaster()` used to identify the role of the mongo server and apply the labels `primary`,  `secondary` accordingly. 

## Arguments

| Argument name             | Description                                         | Default      | 
|---------------------------|-----------------------------------------------------|--------------|
|`--redis-cluster-name`     | redis sentinel master-group-name (must required)    |              |
|`--redis-headless-svc-name`| headless service name of the redis (must required)  |              |
|`--namespace`              | namespace of the redis-ha deployment                | redis        |
|`--pod-selector`           | key=value of to match labels and get the redis pods | app=redis-ha |
|`--redis-sentinel_port`    | redis sentinel port                                 | 26379        |
|`--update-period`          | How frequent this should update the labels (seconds)| 60           |
|`--company-domain`         | company domain to make label key (example.com/role) | redmart.com  |
|`--config-file`            | path to kube config file                            |       -      |
|`--incluster-config`       | load in-cluster kube config                         | True         |
|`--insecure-skip-tls-verify`| skip tls verification                              | False        |
|`--verbose`                 | enable detailed output in the logs                 | False        |
 
## Example Deployment
An example of a deployment can be found in the file `sample-mongo-pod-labeler-deployment.yaml` 
