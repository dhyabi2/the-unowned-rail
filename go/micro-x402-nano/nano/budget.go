package nano

import (
	"fmt"
	"math/big"
	"sync"
)

// Budget is a spend cap in raw that is safe for concurrent use. A nil or
// zero Cap means no cap. Reserve before paying; Release only when no block
// was published.
type Budget struct {
	Cap *big.Int

	mu    sync.Mutex
	spent big.Int
}

// Reserve adds amount to the spent total, or refuses if that would pass Cap.
func (b *Budget) Reserve(amount *big.Int) error {
	b.mu.Lock()
	defer b.mu.Unlock()
	next := new(big.Int).Add(&b.spent, amount)
	if b.Cap != nil && b.Cap.Sign() > 0 && next.Cmp(b.Cap) > 0 {
		return fmt.Errorf("nano: paying %s raw would exceed the budget (spent %s of %s)", amount, &b.spent, b.Cap)
	}
	b.spent.Set(next)
	return nil
}

// Release takes back a reservation whose payment never left.
func (b *Budget) Release(amount *big.Int) {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.spent.Sub(&b.spent, amount)
}

// Spent returns a copy of the total reserved so far.
func (b *Budget) Spent() *big.Int {
	b.mu.Lock()
	defer b.mu.Unlock()
	return new(big.Int).Set(&b.spent)
}
