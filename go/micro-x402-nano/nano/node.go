package nano

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math/big"
	"net/http"
	"time"
)

// Block is what a seller needs from a node's block_info answer.
type Block struct {
	Hash           string
	Account        string // the block's own account: the payer
	Subtype        string // "send", "receive", ...
	Amount         string // raw moved by this block, decimal
	Confirmed      bool
	LinkAsAccount  string // for a send: the recipient
	Representative string
}

// DefaultHTTP is used when a caller passes a nil client.
var DefaultHTTP = &http.Client{Timeout: 10 * time.Second}

// BlockInfo asks the node at url for one block (RPC action block_info with
// json_block). Any transport error, non-200 answer or RPC "error" field is an
// error: the caller must not credit anything on it.
func BlockInfo(ctx context.Context, hc *http.Client, url, hash string) (Block, error) {
	if hc == nil {
		hc = DefaultHTTP
	}
	body, _ := json.Marshal(map[string]string{"action": "block_info", "json_block": "true", "hash": hash})
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return Block{}, err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := hc.Do(req)
	if err != nil {
		return Block{}, fmt.Errorf("nano: node: %w", err)
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return Block{}, fmt.Errorf("nano: node: %w", err)
	}
	if resp.StatusCode != http.StatusOK {
		return Block{}, fmt.Errorf("nano: node answered HTTP %d", resp.StatusCode)
	}
	var r struct {
		Error        string `json:"error"`
		BlockAccount string `json:"block_account"`
		Amount       string `json:"amount"`
		Confirmed    string `json:"confirmed"`
		Subtype      string `json:"subtype"`
		Contents     struct {
			LinkAsAccount  string `json:"link_as_account"`
			Representative string `json:"representative"`
		} `json:"contents"`
	}
	if err := json.Unmarshal(raw, &r); err != nil {
		return Block{}, fmt.Errorf("nano: node: %w", err)
	}
	if r.Error != "" {
		return Block{}, fmt.Errorf("nano: node: %s", r.Error)
	}
	return Block{Hash: hash, Account: r.BlockAccount, Subtype: r.Subtype, Amount: r.Amount,
		Confirmed: r.Confirmed == "true", LinkAsAccount: r.Contents.LinkAsAccount,
		Representative: r.Contents.Representative}, nil
}

// CheckSend returns "" when b is a send of at least price raw to payTo whose
// representative is rep (and which is confirmed, when needConfirmed), and
// otherwise the reason it is refused: not-send, wrong-recipient, short,
// unbound, unconfirmed.
func CheckSend(b Block, payTo [32]byte, price *big.Int, rep string, needConfirmed bool) string {
	if b.Subtype != "send" {
		return "not-send"
	}
	to, err := Decode(b.LinkAsAccount)
	if err != nil || to != payTo {
		return "wrong-recipient"
	}
	amt, ok := new(big.Int).SetString(b.Amount, 10)
	if !ok || amt.Cmp(price) < 0 {
		return "short"
	}
	wantRep, err1 := Decode(rep)
	gotRep, err2 := Decode(b.Representative)
	if err1 != nil || err2 != nil || wantRep != gotRep {
		return "unbound"
	}
	if needConfirmed && !b.Confirmed {
		return "unconfirmed"
	}
	return ""
}
