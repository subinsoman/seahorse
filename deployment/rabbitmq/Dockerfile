#FROM rabbitmq:3.6
FROM rabbitmq:3.9
#FROM rabbitmq:3-management
#FROM rabbitmq:3.6.11
#FROM rabbitmq:3.6.7-alpine

COPY rabbitmq.conf /etc/rabbitmq/
COPY enabled_plugins /etc/rabbitmq/
COPY definitions.json.tmpl /tmp/

COPY startup.sh /tmp/
RUN chown root:root /tmp/startup.sh
RUN chmod 700 /tmp/startup.sh

ENTRYPOINT ["/tmp/startup.sh"]

EXPOSE 61613
EXPOSE 15672
EXPOSE 15674

CMD ["rabbitmq-server"]
