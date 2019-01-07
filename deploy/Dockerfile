FROM alpine:3.7

RUN apk add --no-cache python3 ethtool

COPY tmp/prometheus_client-*.tar.gz /usr/src/
COPY tmp/ethtool-exporter.py /

RUN tar xz -C /usr/src -f /usr/src/prometheus_client-*.tar.gz \
    && cp -pr /usr/src/prometheus_client-*/prometheus_client /usr/lib/python3.6/site-packages \
    && ln -s /usr/sbin/ethtool /sbin/ethtool

EXPOSE 9417

CMD ["python3", "/ethtool-exporter.py", "-l", "0.0.0.0:9417"]
