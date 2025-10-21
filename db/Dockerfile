FROM docker.io/library/postgres:15-alpine

# The postgres image will run any *.sql in /docker-entrypoint-initdb.d on first init
COPY init.sql /docker-entrypoint-initdb.d/00-init.sql


