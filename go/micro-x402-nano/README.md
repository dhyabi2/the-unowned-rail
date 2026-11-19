# go-micro-x402-nano

Nano (`nano:mainnet`, scheme `exact`) for go-micro's x402 wrapper, as a separate integration package that uses the
existing `x402.Facilitator` and `x402.Settler` interfaces. go-micro core is not changed. This package was written
because micro/go-micro#5065 was reviewed with these points:

- keep it out of core, behind the existing interfaces -> `nanox402.Facilitator` implements both;
- use `golang.org/x/crypto/blake2b`, not a custom hash -> the address checksum uses it;
- `x402.Client.Do` parses the amount as an int64, so 0.001 XNO (10^27 raw) is refused before `Payer` is called
  -> `nanox402.Client` parses with `math/big` (`TestGoMicroClientCannotPayNano` keeps the wall on record);
- `Settle` must check `req` -> it re-runs the full verification against `req` before it claims the block.

## Status

Module `github.com/dhyabi2/the-unowned-rail/go/micro-x402-nano`, in this repository under `go/micro-x402-nano/`.
Tested with `go test -race ./...` on Go 1.26.0 against go-micro v6.17.0 (21 tests pass); `go.sum` is written by
`go mod tidy` on Go 1.26 (go-micro v6.17.0 needs it).

```sh
go get github.com/dhyabi2/the-unowned-rail/go/micro-x402-nano@v0.1.0
```

(If the tag `go/micro-x402-nano/v0.1.0` is not yet listed by `git ls-remote --tags`, use `@main`.)

## Seller

```go
seen, err := nano.OpenFileSeen("/var/lib/myservice/nano-seen") // refusals survive a restart
cfg := x402.Config{
    PayTo:             "nano_...",            // your account; checksum-checked
    Network:           nanox402.Network,      // "nano:mainnet"
    Amount:            "1000000000000000000000000000", // raw: 0.001 XNO
    Facilitator:       &nanox402.Facilitator{Node: "https://your-node.example/rpc", Seen: seen},
    RequireSettlement: true,
}
handler = x402.Middleware(cfg)(handler)
```

Verification reads `block_info` from the node you name. A payment is valid only when the block is a confirmed send
of at least the price to `PayTo`, its order id was made for this resource, its representative equals the order
commitment (below), and the block was never credited before. A node error is an error, never a credit.

## Buyer

```go
c := &nanox402.Client{Payer: myWallet, Budget: capInRaw} // Payer signs with your own key
resp, err := c.Do(req)
```

`Payer.Pay` receives one `Send{To, Amount, Representative, Order}` and must publish exactly that send block and
return its hash. The budget is reserved before paying and is given back only if no block was published.

## Binding and replay

A Nano block has no memo. The buyer makes a fresh order id (`resource#<128-bit hex>`) and sets the send block's
representative to `SHA-256("xno-binding/v1/rep|" + order + "|" + payTo + "|" + priceRaw)` as a `nano_` account
(Option C of the xno-call-binding standard v1), so the signed block names one order, one recipient and one price.
The seller claims each block hash once in a `SeenStore`; `nano.OpenFileSeen` keeps the claims in an append-only file
synced before `Settle` returns, so a block cannot be used again after a restart.

## Tests

`go test -race ./...`. The `nano` package imports only the standard library and `x/crypto/blake2b`.
