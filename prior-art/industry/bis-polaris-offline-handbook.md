URL: https://www.bis.org/publications/project-polaris-handbook-offline-payments-cbdc.pdf

# BIS Innovation Hub, Project Polaris: A handbook for offline payments with CBDC (May 2023). Excerpts (pdftotext), sections 4.4-4.6, 5.3.2, 5.5.2, 5.5.8, offline checks and limits.

```
This section introduces the three different modes8 of offline payment.

Before these modes are discussed, it is important to clarify that settlement is the
discharge of a financial obligation and, in the context of offline payments, refers to
the transfer of funds between the payer and the payee.9

Solutions providing offline payments functionality can be categorised as follows:

· Fully offline: Where the payer and payee do not need to connect to a ledger
     system to complete a payment, and any value exchanged is immediately
     transferred to the payee such that they can spend it at the end of the value
     transfer (final settlement occurs offline). Both payer and payee can stay fully
     offline without limitation in time.

· Intermittently offline: Like fully offline, the payer and payee do not need to
     connect to a ledger system to complete a payment, and any value exchanged is
     immediately transferred to the payee such that they can spend it at the end of the
     value transfer (final settlement occurs offline). However, offline risk parameters
     could at some point limit the ability of purses to transact and a purse may have
     to synchronise with the central system intermittently in order to continue to
     function.

· Staged offline: Where the payer and payee do not need to connect to a ledger
     system in order to exchange value, but the value exchanged is not settled on the
     payee until the payee connects to the ledger system (final settlement occurs
     online). Value transferred to the payee cannot be spent until this second stage of
     online settlement has occurred.

Figure 2 illustrates these different modes

8 Some solutions could potentially support more than one mode for risk-management purposes. A solution
       could switch from one mode to another, for example when a certain limit has been reached a fully offline
       solution could switch to either intermittently or staged offline modes, before preventing further
       transactions.

9 Settlement finality refers to when the transfer of funds is irrevocable and unconditional. Settlement finality
       is a legal concept, and this handbook does not use the term. Even though this is a desirable feature in
       offline payments, it may not be feasible in all arrangements since it would ultimately rely on the design of
       the system and the legal framework, for example bankruptcy law. Here "final settlement" is used instead
       to indicate that the transfer is final from a technical point of view, allowing value to be onward spent.

22
Modes of offline payment                                                   BISIH Restricted
                          A handbook for offline payments with CBDC

                                                           Figure 2

Both fully and intermittently offline modes enable the payee to spend the value received at the end of
the transfer. For illustration purposes, for both of these modes this figure shows only two transfers, the
first between purses A and B and the second between purses B and C. In practice solutions would
support more than two transfers, subject to any specific limits.
4.5 Online and offline ledgers

CBDC systems will have a ledger of some form, which is represented as an online and
an offline ledger (which could in practice be a single component) in the logical
architecture.

An online ledger is used by the online CBDC solution and will also provide some of
the features and functionality required to successfully implement offline CBDC
payments.

4.5.1 Fully offline solutions

Depending on the value-form, an offline ledger may not be required, though without
it transaction monitoring will be a challenge. Any online ledger may be unaware of
any offline payments, except for top-ups to and deposits from offline purses.

4.5.2 Staged offline and intermittently offline solutions

Staged offline and intermittently offline solutions require an offline ledger component
to record and reconcile the value in an offline purse. An offline ledger provides a
representation of the current known state of an offline purse. This may not be the
real-time or actual state, as a purse can transact offline, but the ledger is updated at
some point after transactions take place when devices go online.

For both solutions, there can be alternative implementations of the online
ledger/offline ledger design:

                                                                                                                                35
                                                                                                        BISIH Restricted

A handbook for offline payments with CBDC

· Separate balances - The online ledger supports separate online and offline
     balances (no separate offline ledger is required). The online ledger can support
     offline ledger capabilities such as synchronisation with offline purses.

· Separate ledgers -The offline payment solution supplies its own offline ledger.

The offline ledger (or an offline balance associated with the online ledger) should
identify the value held in the offline purse as distinct from the value held in the online
ledger. It is important that any online balances and offline balances are segregated,
otherwise it may be possible for a user to spend the same value both offline and
online and create a double-spend risk25. This segregation applies to the underlying
technical implementation.

The design of the user experience around the difference between offline and online
balances is important, as users could get confused when they have sufficient overall
CBDC value across both online and offline balances but are still unable to pay. It
should be clear to users which balance they are using, though this could be dependent
on the solution. Users should also have the choice to use their offline balance in an
online situation.

Figure 6 illustrates an online transaction failing because there is insufficient online
balance available, even though there is enough offline value to complete the
payment.

25 Segregation of online and offline balances does not eliminate the risk of double spending and other
       measures to mitigate this risk may be required.

36
Online vs offline balance segregation                                                   BISIH Restricted
                                       A handbook for offline payments with CBDC

                                                                    Figure 6

4.6 Offline risk management

Risk management is a critical component of offline payment solutions. Most offline
solutions include specific components for risk management, provided either
separately or as integrated features. The maturity of these components varies, and
further work is required to understand what central banks may need and what
incident management would involve when certain issues are detected. Such
components provide the following features:

4.6.1 Risk parameter management

A risk management component manages risk parameters, for example limits on
balances, transaction value, velocity and volume. This can be enforced locally in the
user device and purse, and could be updated, or pushed, from a central risk
management system when an offline purse comes online to the ledger, in the case of
intermittently or staged offline solutions, or when making a payment when in contact
with a connected device such as a PoS terminal.

Fully offline purses may still support risk parameter updates, but this would only be
possible when the purses come online to top up or deposit funds.

4.6.2 Transaction history management

Many solutions allow transaction history information to be retrieved from purses. This
can be at the level of the transactions undertaken by a specific device or as a history
of the chain of transactions.

                                                                                                                                37
5.3.2 Double-spending

Double-spending is related to a number of the previous threats and refers to
situations where the same offline value is spent a number of times and, without the
possibility of performing an online check, the recipient cannot be sure that the funds
they have received are still in possession of the payer.

It is important to note that the double-spend issue for offline CBDC payments is
different from the well-publicised double-spend issues for public cryptocurrencies. In
the former, trust rests in the tamper-resistant nature of the user device and the purse's
shared cryptographic protocols, while in the latter trust is based on consensus
mechanisms, essentially a form of clearing message. A well-designed offline value
transfer protocol should ensure that double-spend attempts will be rejected by the
payee's purse.

5.5.2 Measures to mitigate the risk of counterfeiting

In general

· It should be difficult to "cash out" of the system; even if it is possible to create
     large amounts of counterfeit value, an attacker should only be able to pay out
     small amounts at a time, mitigating their ability to inject large amounts of
     counterfeit money into the system, which is also limited by risk controls elsewhere,
     for example on counterparty purses or online systems.

Via device breach

· The degree of tamper resistance offered by a user device (provided by secure
     elements, trusted execution environments (TEE) or secure software) and the
     cryptographic security protecting the value in purses and user devices are
     important.

· User devices with a high degree of tamper resistance may be used for any type of
     solution, but would be a key requirement for fully offline solutions.

· User devices with lower degrees of tamper resistance would be unsuitable for fully
     offline solutions, but could be used for intermittently offline solutions, along with
     an appropriate synchronisation regime, as well as for staged offline solutions,
     where payees would need to accept liability if transactions are not settled before
     goods or services are supplied.

· The data elements representing value, offline risk parameters and associated
     cryptographic keys must be stored securely and encrypted in situ to prevent them
     from being cloned and used.

5.5.8 Measures to mitigate double-spending risks

· Any specific payment instruction should be accepted only once and by only one
     receiving purse. Repetition of the exact same payment instruction and attempts
     to spend the same value twice should be rejected by the receiving purse.
     Redirection of a payment instruction intended for one purse to another purse
     should also be rejected by the receiving purse.

· The methods for ensuring these requirements are met are well established, and
     are dependent on the physical security of cryptographic keys and data on
     tamper-resistant devices and cryptographic principles.

· Segregation of online and offline balances in the underlying technical
     implementation could also prevent spending the same value both online and
     offline.

· Intermittently and staged offline solutions could be a mitigating measure as they
     would need to connect online regularly.

5.5.9 Measures to mitigate fraud risks

· User authentication and transaction security methods equivalent to those for
     existing payment solutions in the local jurisdiction should be adopted. This is
     particularly important for offline payments, where online risk and fraud checks are
     not possible.

· It should not be possible for a user that is not the owner of the user device and
     purse to transact with it. In practice, however, the more onerous user
     authentication is, the less likely users are to engage with it.

· In order to mitigate against impersonation, where the payee pretends to be a
     different user, such as a merchant, it may be necessary to include mechanisms
     that allow payees to be identified. However, this may require analysis of the
     relevant use cases and consideration of any privacy issues.

Measures to mitigate lost value risks

Lost user device

If user devices are lost with value loaded onto them, the following issues should be
considered:

· The lost purse can be blocked. However, as it can transact offline, the value may
     be spent before the purse block takes effect.

· Counterparty purses may be updated with block lists containing the missing
     purse. However, as they can transact offline, the value may be spent before these
     are received.

· If the lost purse is in the hands of a criminal, they will drain the value if they are
     able to access it.

58
          detection

Offline limits and checks

Offline payment solutions will need to be able to support checks, such as limits, as
part of a set of countermeasures to reduce the impact of certain risks, for example
counterfeiting or third-party device breaches. These checks would be executed during
an offline payment by the purse software loaded onto the user device.

These checks could include elements such as:

· the maximum offline value that any purse may hold;
· the maximum offline payment that any purse may make;
· the maximum number of times that a purse may transact offline before going

     online;
· the maximum cumulative amount of value that a purse may transact offline before

     going online;
· the maximum value that a purse may transact offline without authenticating itself;

     and
· a list of counterparty purses that should not be transacted with.
Risk management requirements and the capabilities of the purse and the user device
will affect the types of offline checks and limits that can be applied.

                                                                                                                                61
                                                                                           BISIH Restricted

A handbook for offline payments with CBDC

It should be possible to update offline checks and limits (risk parameters), which can
happen when a purse connects to the central system. Further work may be required
to understand the optimal approaches to and performance trade-offs with managing
and updating limits.

Online risk management systems

Online risk management systems may need to analyse transaction data and gross
flows of value from offline purses to detect anomalous behaviour. Offline payment
solutions vary in how this is supported. Some solutions allow for the reconstruction
of all historical offline payments back to a ledger, others support a partial
reconstruction, and fully offline systems provide no offline transaction data. Fully
offline solutions may need to interact with some online system periodically, for
example to top up and deposit value, which could allow risk management systems to
see flows of value or detect potential breaches.

Online risk management systems need to be able to react to breaches when detected.
Possible responses include:

· preventing suspect purses from synchronising with online systems, including
     topping up and depositing value;

· updating risk parameters on purses to reflect changes in overall system status, eg
     restricting the size of offline payments; and

· updating risk parameters on purses to prevent them from transacting with
     suspected rogue purses.

Incident management and response

As part of the risk management for any payment system, how incidents are managed
is crucial, particularly for offline payments.

In the worst case, a breach could lead to offline value being "created" outside of the
central bank's process for issuing CBDC, which would require a coordinated response.
```
