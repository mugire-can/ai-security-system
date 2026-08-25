FROM golang:1.27-alpine AS builder

WORKDIR /app
COPY . .
RUN go build -o alert_dispatcher main.go

FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /app/alert_dispatcher .

EXPOSE 8080
CMD ["./alert_dispatcher", "-port", "8080"]
