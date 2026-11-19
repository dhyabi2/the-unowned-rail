// Package nano holds the Nano pieces of the go-micro x402 integration that do
// not depend on go-micro: address checksums, raw amounts, the order binding,
// the node read, the replay store and the spend cap. It imports only the
// standard library and golang.org/x/crypto/blake2b, and holds no key or seed.
package nano

import (
	"errors"
	"math/big"
	"strings"

	"golang.org/x/crypto/blake2b"
)

const alphabet = "13456789abcdefghijkmnopqrstuwxyz"

// ErrAddress is returned for an address that is not a well-formed nano_ or
// xrb_ account with a valid checksum.
var ErrAddress = errors.New("nano: invalid address")

// Encode returns the nano_ address of a 32-byte public key.
func Encode(pub [32]byte) string {
	sum := checksum(pub[:])
	return "nano_" + encodeBits(pub[:], 52) + encodeBits(sum, 8)
}

// Decode checks an address (nano_ or xrb_ prefix, 60 characters of the Nano
// base32 alphabet, 5-byte BLAKE2b checksum) and returns its public key.
func Decode(addr string) ([32]byte, error) {
	var pub [32]byte
	var body string
	switch {
	case strings.HasPrefix(addr, "nano_"):
		body = addr[5:]
	case strings.HasPrefix(addr, "xrb_"):
		body = addr[4:]
	default:
		return pub, ErrAddress
	}
	if len(body) != 60 {
		return pub, ErrAddress
	}
	keyN, ok := decodeBits(body[:52])
	if !ok || keyN.BitLen() > 256 {
		return pub, ErrAddress
	}
	keyN.FillBytes(pub[:])
	sumN, ok := decodeBits(body[52:])
	if !ok {
		return pub, ErrAddress
	}
	var got [5]byte
	sumN.FillBytes(got[:])
	want := checksum(pub[:])
	for i := range got {
		if got[i] != want[i] {
			return pub, ErrAddress
		}
	}
	return pub, nil
}

// Canonical returns the nano_ form of a valid address (xrb_ is rewritten).
func Canonical(addr string) (string, error) {
	pub, err := Decode(addr)
	if err != nil {
		return "", err
	}
	return Encode(pub), nil
}

// checksum is BLAKE2b-40 of the key, byte-reversed, as the protocol defines.
func checksum(pub []byte) []byte {
	h, _ := blake2b.New(5, nil) // size 5 with no key never errors
	h.Write(pub)
	s := h.Sum(nil)
	for i, j := 0, len(s)-1; i < j; i, j = i+1, j-1 {
		s[i], s[j] = s[j], s[i]
	}
	return s
}

func encodeBits(data []byte, chars int) string {
	n := new(big.Int).SetBytes(data)
	out := make([]byte, chars)
	mask := big.NewInt(31)
	d := new(big.Int)
	for i := chars - 1; i >= 0; i-- {
		d.And(n, mask)
		out[i] = alphabet[d.Int64()]
		n.Rsh(n, 5)
	}
	return string(out)
}

func decodeBits(s string) (*big.Int, bool) {
	n := new(big.Int)
	for i := 0; i < len(s); i++ {
		v := strings.IndexByte(alphabet, s[i])
		if v < 0 {
			return nil, false
		}
		n.Lsh(n, 5)
		n.Or(n, big.NewInt(int64(v)))
	}
	return n, true
}
