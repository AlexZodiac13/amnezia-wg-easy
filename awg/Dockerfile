FROM golang:1.25-alpine AS builder

RUN apk add --no-cache git
RUN go install github.com/amnezia-vpn/amneziawg-go@latest

FROM alpine:3.20

RUN apk add --no-cache \
    bash \
    iproute2 \
    iptables \
    wireguard-tools

COPY --from=builder /go/bin/amneziawg-go /usr/local/bin/amneziawg-go
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]