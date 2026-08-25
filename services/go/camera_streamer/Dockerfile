FROM golang:1.27-alpine AS builder

WORKDIR /app
COPY . .
RUN go build -o camera_streamer main.go

FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /app/camera_streamer .

EXPOSE 8081
CMD ["./camera_streamer", "-port", "8081"]
