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
import time

from kubernetes import config, client
from redis.sentinel import Sentinel


def get_get_redis_sentinel(hostname, port=26379, socket_timeout=0.5):
    logging.debug(f"Connecting to redis sentinel", )
    return Sentinel([(hostname, port)], socket_timeout)


def is_master(sentinel, master_group_name):
    state = sentinel.sentinel_masters()
    return sentinel.check_master_state(state, master_group_name)


def get_redis_pods(k8s_api):
    redis_host_names = []
    logging.debug(f"getting redis pods for matched label(s) {args.pod_selector} in namespace {args.namespace}")
    pod_details = k8s_api.list_namespaced_pod(namespace="{}".format(args.namespace),
                                              label_selector="{}".format(args.pod_selector))
    for item in pod_details.items:
        redis_host_names.append((item.metadata.name, item.metadata.generate_name[:-1], item.metadata.namespace))
    return redis_host_names


def label_redis_pods(k8s_api, pod_name, label):
    logging.info(f"applying label '{label}' to {pod_name}")
    return k8s_api.patch_namespaced_pod(name=pod_name, namespace="{}".format(args.namespace), body=label)


def generate_pod_label_body(label, domain):
    patch_content = {"kind": "Pod", "apiVersion": "v1", "metadata": {"labels": {f"{domain}/role": label}}}
    return patch_content


def find_redis_and_label(v1):
    pod_details = get_redis_pods(v1)
    for pod_data in pod_details:
        my_client = get_get_redis_sentinel(pod_data[0] + "." + pod_data[1] + "." + pod_data[2], 26379)
        if is_master(my_client):
            redis_role = "master"
            logging.debug(f"{pod_data[0]} is a master")
        else:
            redis_role = "slave"
            logging.debug(f"{pod_data[0]} is a slave")
        label_redis_pods(v1, pod_data[0], generate_pod_label_body(redis_role, args.domain))


# MAIN
parser = argparse.ArgumentParser(description="Checking redis pods and labelling them with master/slave accordingly")
parser.add_argument('--dry-run', dest='dry_run', action='store_true', default=False)
parser.add_argument('--namespace', dest='namespace', required=False, default='redis')
parser.add_argument('--pod-selector', dest='pod_selector', default='app=redis-ha', required=False)
parser.add_argument('--company-domain', dest='domain', default='redmart.com', required=False)
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
