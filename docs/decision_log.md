# Decision log

Decisions that shape the results, with the reason and what was rejected. Newest stage last.

## Stage 1: data, leakage and the rules baseline

**Score only TRANSFER and CASH_OUT.** All fraud in PaySim is in these two types. The other types
(payments, cash-in, debit) are allowed by default and monitored separately. This removes more than
half the traffic from the model's job without missing a single fraud.

**Exclude post-transaction balances and "balance errors".** `newbalanceOrig`, `newbalanceDest`
and the gap between balance change and amount separate fraud almost perfectly, which is why many
public notebooks report 0.99+ scores. A real system decides *before* the money moves, so these
values do not exist yet; in a real ledger the "error" is zero by construction, so in PaySim it is a
simulator artefact. They are kept only for the leakage audit, which shows how strong they are.

**Exclude `isFlaggedFraud` as a feature.** It is the output of the existing rule system. It is kept
as the "current system" baseline instead.

**Behaviour features use only earlier hours.** The data has no order within an hour, so a window
that included the current hour could let a transaction see activity that happened after it. Every
history feature uses `RANGE ... 1 PRECEDING`. Two tests prove it: adding a future transaction, or
another transaction in the same hour, changes no existing feature.

**History on the recipient side.** Almost every sender in PaySim appears once, so sender velocity
features carry little signal. Recipients repeat, and money mules show up as recipients that receive
from many senders in a short time. Sender history is kept (`orig_prior_txns`) so the audit shows this.

**Time-based split inside the realistic period, plus a separate stress test.** A per-day profile
showed that fraud stays steady at about 260 a day for the whole month, while normal traffic is
realistic (150,000-200,000 transactions a day) only on days 1-2 and 6-17. On days 3-5 and 18-31 it
almost stops, and day 31 is 272 transactions that are all fraud. These are simulator artefacts. A
first split that tested on days 24-31 had a 2.6% fraud rate, 14 times the normal 0.19%, which would
have flattered every precision number. So:

| Period | Days | Use |
| --- | --- | --- |
| Train | 1-13 | fit the models |
| Valid | 14-15 | tune them |
| Test | 16-17 | headline results, at a realistic fraud rate |
| Shifted | 18-31 | separate stress test: how the model behaves when traffic suddenly changes |

A random split was rejected: it would let the model learn from the same days (and the same mule
accounts) it is tested on, which overstates performance.

**The ceiling under a budget.** At about 260 frauds a day and 200 reviews a day, no method can catch
more than roughly 75% of fraud by count. Results are reported against that ceiling.

**Precision-recall metrics and alert budgets.** With fraud around 0.1% of all transactions, ROC-AUC
looks good even for weak models. The headline numbers are PR-AUC, recall and **fraud value caught**
within a **daily alert budget** (200 reviews per day), because that is how a fraud operations team
is measured.

**The existing flag barely works.** On the first run, `isFlaggedFraud` caught 10 of 2,120 frauds
in the test days. The three rules together caught 96% of fraud, but only by raising about 7,000 alerts
a day; limited to the top 200 a day, they caught about a third. This is the operational problem the
model has to solve: not finding fraud at all costs, but finding it within the team's capacity.

**A rules baseline first.** Three readable rules (large amount, account drained, large transfer to
a new recipient) set the bar. Any model in stage 2 must beat them on the same test days and the same
budget, or it has not earned its complexity.
