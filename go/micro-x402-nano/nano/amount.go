package nano

import (
	"errors"
	"math/big"
)

// RawPerXNO is 10^30, the number of raw in one XNO. It is derived, not typed
// out, so a digit cannot be lost.
var RawPerXNO = new(big.Int).Exp(big.NewInt(10), big.NewInt(30), nil)

// maxRaw is 2^128 - 1: a Nano balance is a 128-bit unsigned integer.
var maxRaw = new(big.Int).Sub(new(big.Int).Lsh(big.NewInt(1), 128), big.NewInt(1))

// ErrAmount is returned for an amount that is not a positive decimal integer
// of raw that fits in 128 bits.
var ErrAmount = errors.New("nano: invalid raw amount")

// ParseRaw parses a price in raw. It accepts only ASCII digits (no sign, no
// space, no exponent), at most 39 of them, greater than zero and at most
// 2^128 - 1. Unlike strconv.ParseInt it holds any real Nano price: 0.001 XNO
// is 10^27 raw, far above the int64 limit of about 9.2 * 10^18.
func ParseRaw(s string) (*big.Int, error) {
	if len(s) == 0 || len(s) > 39 {
		return nil, ErrAmount
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return nil, ErrAmount
		}
	}
	n, ok := new(big.Int).SetString(s, 10)
	if !ok || n.Sign() <= 0 || n.Cmp(maxRaw) > 0 {
		return nil, ErrAmount
	}
	return n, nil
}
