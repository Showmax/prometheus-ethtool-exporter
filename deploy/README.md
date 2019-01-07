# How to build

```./buils.sh```


# How to use with plain Docker

```
docker pull drdivano/ethtool-exporter
docker run -d --name ethtool-exporter --network=host drdivano/ethtool-exporter
```

Check that it works:

```
curl http://localhost:9417
```


# How to deploy to Kubernetes

Provided Kubernetes daemonset will download a pre-built image from Docker Hub.

```
kubectl apply -f k8s-daemonset.yaml
```

Wait for the pods to start:

```
kubectl get pods -l app=ethtool-exporter -o wide
```

Check that the exporter works:

```
curl http://EXPORTER-POD-IP:9417/metrics
```

If Prometheus has been configured to read Kubernetes annotations, then
it will start scraping the metrics automatically.
