INSTRUCTION:

1. DO NOT INCLUDE COMMENTS OR EXPLANATION UNLESS REQUIRED
2. DO NOT INCLUDE EMOJIS OR ANYTHING
3. ALWAYS ASK CLARIFYING QUESTION UNTIL YOU ARE 99.9% CONFIDENT THAT YOU WILL BE ABLE TO ANSWER MY QUESTION CORRECTLY


overview:

create a project that will fetch data from https://api.opendota.com/api, store it in a PostgreSQL database using a medallion architecture (bronze / silver / gold), then connect it to a power bi.

steps:

1. extract all the endpoints of the api end-to-end and store the raw payloads as JSON files (bronze-ready)
2. design the bronze schema and load the raw JSON into postgres
3. transform into silver and gold layers (dbt, SQL)
4. setup later the power bi once the transformation is complete

this is a project for junior data engineer role as an entry portfolio.

we should be able to show the data flow from the source up to the dashboard, this includes the essential processes like using dbt, orchestrator, mastery of python and sql, usage of one db (which is for this project, we are going to use postgres). if the project will become big enough, we can implement using the pyspark. processes can be improve along the way, adjusting whatever this project needs.

DETAILS:

we are going to use this api, the details are as follows:

api: https://api.opendota.com/api
price: free
key required? no
call limit: 3000 per day
rate limit: 60 calls per minute
