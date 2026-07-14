FROM rust:1.97-alpine as builder

RUN apk add --no-cache musl-dev
WORKDIR /app
COPY . .
RUN cargo build --release

FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /app/target/release/video_optimizer .

EXPOSE 8082
CMD ["./video_optimizer"]
