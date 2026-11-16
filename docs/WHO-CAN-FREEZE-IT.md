# Who can freeze it?

Four claims. Each one links to the code or documentation it rests on. Every source is a file in a public GitHub repository and was read on **2026-11-16**. Open the links and check them yourself.

## 1. Circle's stablecoin contract has a function that blacklists an address

The repository [circlefin/stablecoin-evm](https://github.com/circlefin/stablecoin-evm) holds "the smart contracts used by Circle's stablecoins on EVM-compatible blockchains" ([README.md](https://github.com/circlefin/stablecoin-evm/blob/master/README.md)). Its design document says the token contract (`FiatToken`) allows "freezing of individual addresses" ([doc/tokendesign.md](https://github.com/circlefin/stablecoin-evm/blob/master/doc/tokendesign.md), line 5).

`contracts/v1/Blacklistable.sol`, default branch `master`:

```solidity
function blacklist(address _account) external onlyBlacklister {
    _blacklist(_account);
    emit Blacklisted(_account);
}
```

Source: [Blacklistable.sol](https://github.com/circlefin/stablecoin-evm/blob/master/contracts/v1/Blacklistable.sol), line 71. `onlyBlacklister` (line 38) lets only one address, the `blacklister` role, call it. `updateBlacklister` (line 89) is `onlyOwner`, so the contract owner sets who that is. `unBlacklist` (line 80) undoes it.

## 2. A blacklisted address cannot send or receive the token

The same repository's [doc/tokendesign.md](https://github.com/circlefin/stablecoin-evm/blob/master/doc/tokendesign.md):

> `blacklister` - prevent all transfers to or from a particular address, and prevents that address from minting or burning (line 18)

> A blacklisted address will be unable to call `transfer` or `transferFrom`, and will be unable to receive tokens. (lines 32-33)

The code matches: in [FiatTokenV1.sol](https://github.com/circlefin/stablecoin-evm/blob/master/contracts/v1/FiatTokenV1.sol), `transfer` carries `notBlacklisted(msg.sender)` and `notBlacklisted(to)` (lines 292-293), and `transferFrom` carries the same check on the caller, the sender and the receiver (lines 267-269).

## 3. On Nano, only the key holder can write to an account

[nanocurrency/nano-docs, `docs/integration-guides/the-basics.md`](https://github.com/nanocurrency/nano-docs/blob/f81289d/docs/integration-guides/the-basics.md) (commit f81289d, line 8):

> Every account (private/public key pair) has their own blockchain (account-chain). Only the holder of the private key may sign and publish blocks to their own account-chain.

## 4. Nano's documentation says it has no transaction fee

[nanocurrency/nano-docs, `docs/what-is-nano/overview.md`](https://github.com/nanocurrency/nano-docs/blob/f81289d/docs/what-is-nano/overview.md) (commit f81289d, line 11):

> With ultrafast transactions and zero fees on a secure, green and decentralized network ...

Also [`docs/protocol-design/introduction.md`](https://github.com/nanocurrency/nano-docs/blob/f81289d/docs/protocol-design/introduction.md), line 23: "Nano is a low-latency, feeless, scalable, and environmentally friendly cryptocurrency". No network fee on the transfer does not mean converting in and out is free: see [FEELESS-IS-NOT-FREE-TO-CONVERT.md](FEELESS-IS-NOT-FREE-TO-CONVERT.md).

## What this page does not claim

These are not sourced here, so this page does not state them:

- That the blacklist has been used on any given address. That needs a link to an on-chain `Blacklisted` event.
- How any x402 facilitator screens payers. That needs the facilitator's own documentation.
- That Nano has "no function that freezes an account". That is a claim that something is absent. Claim 3 is the sourced positive form: only the key holder signs that account's blocks.

## In one line

> Circle's stablecoin contract has a `blacklist(address)` function that stops transfers to or from that address ([Blacklistable.sol](https://github.com/circlefin/stablecoin-evm/blob/master/contracts/v1/Blacklistable.sol), [tokendesign.md](https://github.com/circlefin/stablecoin-evm/blob/master/doc/tokendesign.md)). On Nano, only the holder of an account's key can sign its blocks ([the-basics.md](https://github.com/nanocurrency/nano-docs/blob/f81289d/docs/integration-guides/the-basics.md)).
