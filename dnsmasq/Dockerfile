FROM alpine:3.20

RUN apk add --no-cache dnsmasq

CMD ["dnsmasq", "-k", "--conf-file=/etc/dnsmasq.conf", "--log-facility=-"]
