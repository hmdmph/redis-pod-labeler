#!/usr/bin/python3

# Copyright 2019 Redmart Pte Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import logging
import subprocess
import time

from kubernetes import config, client

POD_NAME_ANNOTATION = "statefulset.kubernetes.io/pod-name"
DEFAULT_CLUSTER_DOMAIN = "cluster.local"
REDIS_HA = "redis-ha"


def get_redis_master_svc_ip(redis_host, sentinel_port, sentinel_cluster_name):
    result_1 = subprocess.run(
        ['redis-cli', '-h', redis_host, '-p', str(sentinel_port), 'sentinel', 'get-master-addr-by-name', sentinel_cluster_name],
        stdout=subprocess.PIPE)
    result_2 = subprocess.run(['sed', '-n', '1p'], input=result_1.stdout, stdout=subprocess.PIPE)
    result_3 = subprocess.run(['grep', '-E', '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}'], input=result_2.stdout,
                              stdout=subprocess.PIPE)
    return str(result_3.stdout.decode('utf-8'))


def get_redis_pods_with_roles(k8s_api, master_svc_ip):
    redis_pods_with_role = []
    services = k8s_api.list_namespaced_service(namespace="{}".format(args.namespace),
                                               label_selector="{}".format(args.svc_selector))
    logging.debug(f"getting list of all services in namespace {args.namespace}")
    for service in services.items:
        if is_redis_ha_service(service.spec.selector):
            redis_pod_name = service.spec.selector[POD_NAME_ANNOTATION].strip()
            logging.debug("|" + service.spec.cluster_ip + "|" + master_svc_ip + "|" + redis_pod_name)
            if str(service.spec.cluster_ip.strip()) == str(master_svc_ip.strip()):
                logging.info("master: " + redis_pod_name)
                redis_pods_with_role.append(("master", redis_pod_name))
            else:
                logging.info("slave: " + redis_pod_name)
                redis_pods_with_role.append(("slave", redis_pod_name))
        else:
            logging.debug(f"not redis cluster related service - {str(service.spec.selector)}")

    return redis_pods_with_role


def is_redis_ha_service(service_selector):
    logging.debug(f"{str(service_selector)}")
    if POD_NAME_ANNOTATION.strip() in service_selector and 'app' in service_selector and service_selector['app'].strip() == REDIS_HA:
        return True
    else:
        return False


def label_redis_pods(k8s_api, pod_name, label):
    logging.info(f"applying label '{label}' to {pod_name}")
    return k8s_api.patch_namespaced_pod(name=pod_name, namespace="{}".format(args.namespace), body=label)


def generate_pod_label_body(label, domain):
    patch_content = {"kind": "Pod", "apiVersion": "v1", "metadata": {"labels": {f"{domain}/role": label}}}
    return patch_content


def find_redis_and_label(v1):
    master_ip = get_redis_master_svc_ip(args.headless_name + '.' + args.namespace, args.sentinel_port, args.cluster_name)
    logging.info('Master Is: ' + master_ip)
    pod_details = get_redis_pods_with_roles(v1, master_ip)
    for pod_data in pod_details:
        logging.debug(f"POD:  {pod_data[0]}, {pod_data[1]}")
        label_redis_pods(v1, pod_data[1], generate_pod_label_body(pod_data[0], args.domain))


# MAIN
parser = argparse.ArgumentParser(description="Checking redis pods and labelling them with master/ slave accordingly")
parser.add_argument('--dry-run', dest='dry_run', action='store_true', default=False)
parser.add_argument('--namespace', dest='namespace', required=False, default='redis')
parser.add_argument('--svc-selector', dest='svc_selector', default='app=redis-ha', required=False)
parser.add_argument('--redis-cluster-name', dest='cluster_name', required=True)
parser.add_argument('--redis-headless-svc-name', dest='headless_name', required=True)
parser.add_argument('--redis-sentinel_port', dest='sentinel_port', default=26379, required=False)
parser.add_argument('--cluster-domain', dest='cluster_domain', default=DEFAULT_CLUSTER_DOMAIN, required=False)
parser.add_argument('--company-domain', dest='domain', default='redis.io', required=False)
parser.add_argument('--config-file', dest='config_file', required=False)
parser.add_argument('--incluster-config', dest='incluster_config', action='store_true', required=False, default=False)
parser.add_argument('--insecure-skip-tls-verify', dest='skip_tls_verify', action='store_true', required=False, default=False)
parser.add_argument('--verbose', dest='verbose', action='store_true', required=False, default=False)
parser.add_argument('--update-period', dest='sleep_seconds', required=False, default=60)

args = parser.parse_args()

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.DEBUG if args.verbose else logging.INFO
)

logging.captureWarnings(True)
logging.info("Starting redis replica labeler...")
logging.info(f"Dry run: {args.dry_run}")

if args.config_file is None:
    logging.info("Loading current kubernetes cluster config")
    config.load_incluster_config()
else:
    logging.info("Loading kubernetes from passed config file")
    config.load_kube_config(config_file=args.config_file)

logging.info(f"SSL Verify: {not args.skip_tls_verify}")
if args.skip_tls_verify:
    conf = client.Configuration()
    conf.verify_ssl = False
    conf.debug = False
    client.Configuration.set_default(conf)

v1Api = client.CoreV1Api()

while True:
    find_redis_and_label(v1Api)
    logging.info(f"Sleeping {args.sleep_seconds}...")
    time.sleep(int(args.sleep_seconds))
