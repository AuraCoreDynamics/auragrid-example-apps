FROM golang:1.22-alpine AS builder

WORKDIR /app
COPY main.go .
RUN go build -o glutton main.go

FROM alpine:latest

WORKDIR /app
COPY --from=builder /app/glutton .

ENTRYPOINT ["./glutton"]
