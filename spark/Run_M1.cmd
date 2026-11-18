@echo off
setlocal
cd /d "%~dp0.."
set "PKGS=org.postgresql:postgresql:42.7.4,io.delta:delta-spark_2.12:3.0.0"
set "SPARK=docker compose -f docker-compose.spark.yml run --rm spark /opt/spark/bin/spark-submit --master local[2] --driver-memory 1g --conf spark.jars.ivy=/tmp/.ivy2 --packages %PKGS%"

echo Building M1a gold tables in Delta...
%SPARK% /opt/spark/smoke/jobs/build_gold.py
if errorlevel 1 exit /b 1

echo Running parity check against dbt...
%SPARK% /opt/spark/smoke/jobs/parity_check.py
if errorlevel 1 exit /b 1
echo M1a completed and parity passed.
endlocal
