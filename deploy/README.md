# How to build

```./buils.sh```


# How to use with plain Docker

```
docker pull drdivano/ethtool-exporter
docker run -d --name ethtool-exporter --network=host drdivano/ethtool-exporter
```

Check the metrics:

```
curl http://localhost:9417
```


# How to deploy to Kubernetes

```
kubectl apply -f k8s.yaml
```

If Prometheus has been configured to read Kubernetes annotations, then
it will start scraping the metrics automatically.
