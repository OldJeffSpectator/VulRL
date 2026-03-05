#!/bin/bash

# Activate virtual environment
source /data1/jph/VulRL/.venv/bin/activate

# Load API key
export OPENAI_API_KEY=$(cat /data1/jph/apikey.txt)
# export OPENAI_API_BASE="https://api.openai.com/v1"  # Optional, defaults to OpenAI

# THe list of 30 cves from different catagory to test the interactive poc generation
# /data1/jph/vulhub/jboss/CVE-2017-12149 (replaced 1panel/CVE-2024-39907 - post-auth issue)
# /data1/jph/vulhub/activemq/CVE-2022-41678
# /data1/jph/vulhub/adminer/CVE-2021-43008
# /data1/jph/vulhub/airflow/CVE-2020-11978
# /data1/jph/vulhub/apache-druid/CVE-2021-25646
# /data1/jph/vulhub/confluence/CVE-2023-22527
# /data1/jph/vulhub/django/CVE-2020-9402
# /data1/jph/vulhub/drupal/CVE-2018-7600
# /data1/jph/vulhub/elasticsearch/CVE-2014-3120
# /data1/jph/vulhub/flink/CVE-2020-17518
# /data1/jph/vulhub/gitlab/CVE-2021-22205
# /data1/jph/vulhub/grafana/CVE-2021-43798
# /data1/jph/vulhub/influxdb/CVE-2019-20933
# /data1/jph/vulhub/jenkins/CVE-2018-1000861
# /data1/jph/vulhub/joomla/CVE-2017-8917
# /data1/jph/vulhub/kafka/CVE-2023-25194
# /data1/jph/vulhub/laravel/CVE-2021-3129
# /data1/jph/vulhub/metabase/CVE-2023-38646
# /data1/jph/vulhub/mongo-express/CVE-2019-10758
# /data1/jph/vulhub/mysql/CVE-2012-2122
# /data1/jph/vulhub/neo4j/CVE-2021-34371
# /data1/jph/vulhub/nginx/CVE-2017-7529
# /data1/jph/vulhub/phpmyadmin/CVE-2016-5734
# /data1/jph/vulhub/redis/CVE-2022-0543
# /data1/jph/vulhub/shiro/CVE-2010-3863
# /data1/jph/vulhub/spring/CVE-2017-4971
# /data1/jph/vulhub/tomcat/CVE-2020-1938
# /data1/jph/vulhub/weblogic/CVE-2018-2894
# /data1/jph/vulhub/zabbix/CVE-2016-10134
# /data1/jph/vulhub/node/CVE-2017-16082

# folder to save the result of test 30 cves
result_path="/data1/jph/tmp/result_test_30"

# CVE-2024-39907 (1panel) - Skipped: Post-auth SQLi, requires credentials
# Replaced with JBoss CVE-2017-12149 (deserialization RCE)
python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2017-12149" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2022-41678" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2021-43008" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2020-11978" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2021-25646" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2023-22527" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2020-9402" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2018-7600" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2014-3120" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2020-17518" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2021-22205" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2021-43798" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2019-20933" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2018-1000861" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2017-8917" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2023-25194" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2021-3129" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2023-38646" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2019-10758" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2012-2122" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2021-34371" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2017-7529" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2016-5734" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2022-0543" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2010-3863" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2017-4971" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2020-1938" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2018-2894" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2016-10134" \
  --result-dir $result_path

python interactive_poc_generator.py \
  --vulhub-dir ~/vulhub \
  --cve-filter "CVE-2017-16082" \
  --result-dir $result_path

echo "All 30 CVEs processed!"
