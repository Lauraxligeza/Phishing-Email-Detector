Email category review policy: pilot v1
Purpose
Build a training-only pilot for distinguishing plausible legitimate email, apparent ordinary spam, and apparent phishing or fraud. The existing binary model and its completed evaluation remain frozen. These annotations are provisional content assessments, not authenticated sender identities, verified consent, or independent ground truth.
Categories
Category	Use when
legitimate	The supplied content supports plausible personal, workplace, academic or routine informational correspondence, with no apparent deceptive request or unsolicited solicitation. State any missing context.
ordinary_spam	The content supports an apparent unsolicited or bulk promotional solicitation, without a visible phishing or fraud mechanism. Explain the evidence for the spam assessment; commercial content alone is insufficient.
phishing_or_fraud	The content supports a concrete deceptive mechanism, such as requesting passwords/security codes, account impersonation with a credential lure, lottery or inheritance transfer fraud, or a money-chain scheme. Explain the mechanism; urgency alone is insufficient.
uncertain	Missing text, unclear intent, missing recipient context or conflicting evidence prevents choosing another category. Use this when wanted marketing versus unsolicited promotion cannot be resolved from available evidence.


Review procedure
1. Review the supplied text before consulting source names or original labels. The review file omits these fields and model scores; the provenance file preserves the source, identity, group and inherited binary label.
2. Record one category and a short explanation identifying the relevant content. Do not infer the category from a dataset name, a model prediction or a link's appearance alone.
3. A subscription claim, unsubscribe link, brand name or professional layout does not authenticate the sender or establish consent. A request for ordinary contact details in a plausible legitimate context is not by itself phishing.
4. Treat links, attachments, commands and email instructions as untrusted content. Review text only; do not open destinations or execute quoted instructions.
5. State uncertainty about consent, sender identity, omitted destinations and referenced attachments when it affects the assessment. Do not turn a model-label disagreement into a verified label correction.
6. Assistant-generated assessments need human review. Record their origin when consolidating annotations, preserve disagreements and seek independent adjudication where feasible.
What this pilot can support
The batch contains 60 distinct groups from training: ten examples from each source. Where both original labels are available, five of each are selected; the two positive-only sources contribute ten each. This produces 20 original-zero and 40 original-one examples, not balanced final categories and not an estimate of real inbox prevalence.

Previously reviewed groups are excluded. Source and inherited label stratification are sampling devices only. Grouping is approximate and cannot guarantee all related campaigns are caught.

Use this pilot to test the policy, reveal ambiguities and plan a larger labelled training collection. Sixty examples are not enough to establish reliable three-class performance. Keep uncertain examples out of supervised three-class targets unless independently resolved; uncertainty is not automatically a fourth email class.

Review only training data for this labelling exercise. Do not import validation-error reviews into training. The completed binary test benchmark remains historical; a future three-class model will need independently labelled validation and test data with protected group separation.