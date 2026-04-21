FROM golang:1.25-alpine AS awg-go-builder

RUN apk add --no-cache git
RUN go install github.com/amnezia-vpn/amneziawg-go@latest

FROM alpine:3.20 AS awg-tools-builder

RUN apk add --no-cache bash build-base git linux-headers
WORKDIR /src
RUN git clone --depth 1 https://github.com/amnezia-vpn/amneziawg-tools.git .
RUN make -C src PLATFORM=linux WITH_WGQUICK=yes WITH_BASHCOMPLETION=no WITH_SYSTEMDUNITS=no
RUN make -C src PLATFORM=linux PREFIX=/usr DESTDIR=/out WITH_WGQUICK=yes WITH_BASHCOMPLETION=no WITH_SYSTEMDUNITS=no install

FROM alpine:3.20

RUN apk add --no-cache \
    bash \
    iproute2 \
    iptables \
    openresolv \
    python3 \
    py3-pip

RUN pip3 install --no-cache-dir --break-system-packages qrcode[pil]

COPY --from=awg-go-builder /go/bin/amneziawg-go /usr/local/bin/amneziawg-go
COPY --from=awg-tools-builder /out/usr/bin/awg /usr/local/bin/awg
COPY --from=awg-tools-builder /out/usr/bin/awg-quick /usr/local/bin/awg-quick
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh /usr/local/bin/awg /usr/local/bin/awg-quick

ENTRYPOINT ["/entrypoint.sh"]