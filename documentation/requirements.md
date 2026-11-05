# Requirement catalogue · JurisFonte

Single source for the definition of the 23 functional and 10 quality
requirements of the September 2026 solution proposal. The IDs are permanent and
the titles allow direct links. Acceptance criteria and evidence live in the Jira
user stories; delivery stages live in the Roadmap.

The IDs keep the Portuguese prefixes **RF** (*requisito funcional*) and **RNF**
(*requisito não funcional*). They are not translated: they are the identifiers
used in Jira, in Confluence and in the repository's autolink configuration, and
renaming them would break every link already written in a branch, a commit or a
pull request.

Each requirement carries its own anchor, so that
`documentation/requirements.md#RF18` opens the matching section. That is the
destination used by the commits and pull requests described in the
contribution guide, `CONTRIBUTING.md`.

| | | | |
|---|---|---|---|
| [RF01](#RF01) Search by term or exact phrase | [RF07](#RF07) Paging of the results | [RF13](#RF13) Unanimity or majority | [RF19](#RF19) Laws, articles and precedents cited |
| [RF02](#RF02) Syllabus excerpt and official source | [RF08](#RF08) Coverage of the base | [RF14](#RF14) Export of the scope | [RF20](#RF20) Semantically close decisions |
| [RF03](#RF03) Filters by court and period | [RF09](#RF09) Evolution of the volume over time | [RF15](#RF15) Comparison between courts | [RF21](#RF21) Report of an incorrect classification |
| [RF04](#RF04) Decision detail | [RF10](#RF10) Proportion of appeal outcomes | [RF16](#RF16) Status of the sources and last collection | [RF22](#RF22) Divergences between panels |
| [RF05](#RF05) Volume of decisions by court | [RF11](#RF11) Additional legal filters | [RF17](#RF17) Saved search | [RF23](#RF23) Decisions to the contrary |
| [RF06](#RF06) Ordering by relevance or date | [RF12](#RF12) Documents behind the indicators | [RF18](#RF18) Concentration by judging body and reporting judge | |

| | | | |
|---|---|---|---|
| [RNF01](#RNF01) Traceability | [RNF04](#RNF04) Performance | [RNF07](#RNF07) Data quality | [RNF10](#RNF10) Maintainability |
| [RNF02](#RNF02) Security | [RNF05](#RNF05) Scalability | [RNF08](#RNF08) Observability | |
| [RNF03](#RNF03) Privacy | [RNF06](#RNF06) Availability | [RNF09](#RNF09) Accessibility | |

---

## Functional requirements

### RF01 · Search by term or exact phrase <a id="RF01"></a>

**Objective.** Find decisions from the expression the user supplies.

**Expected behaviour.** Offer search by term and by exact phrase, with visible
syntax. Preserve the expression submitted and present total, results, loading,
error and guidance when there are no results.

**Verification.** Compare term and exact-phrase searches against known documents
and check the results.

### RF02 · Syllabus excerpt and official source <a id="RF02"></a>

**Objective.** Assess a result and check its origin before citing it.

**Expected behaviour.** Show a contextualised excerpt of the syllabus,
highlighting the term found, and a link to the official document. Where there is
no highlightable occurrence, show the beginning of the syllabus. Links
identified as invalid must state the reason for the unavailability.

**Verification.** Check excerpts, highlights and the opening of the
corresponding document at the official source.

### RF03 · Filters by court and period <a id="RF03"></a>

**Objective.** Narrow the search to the scope of interest.

**Expected behaviour.** Allow selecting one or several courts and supplying a
start and an end date. Selected courts form a union; the period and the search
expression narrow that set. Include the boundary dates, prevent an inverted
interval and recalculate the total. The date field used must be identified in
the interface.

**Verification.** Test filters in isolation and combined, the boundaries of the
interval, and a search with no filters.

### RF04 · Decision detail <a id="RF04"></a>

**Objective.** Read the decision and assess its application to the case.

**Expected behaviour.** Present the reporting judge, the judging body, the dates
and the complete syllabus. Do not truncate the syllabus; identify unavailable
metadata. Keep access to the origin and allow returning to the context of the
search.

**Verification.** Open decisions with long syllabuses and incomplete metadata
and compare the display with the source data.

### RF05 · Volume of decisions by court <a id="RF05"></a>

**Objective.** Identify how the documents are distributed between courts.

**Expected behaviour.** Count the decisions of the whole searched scope, not
only of the page shown. Identify each court and allow consulting the documents
that make up its total. State that frequency does not represent legal
relevance.

**Verification.** Check the totals per court and their sum against the same
document query.

### RF06 · Ordering by relevance or date <a id="RF06"></a>

**Objective.** Consult first the results most pertinent to the search, or the
most recent.

**Expected behaviour.** Offer ordering by relevance and by date, preserving the
expression and the filters. Document the relevance rule, the date field and the
tie-break. Search relevance does not represent legal importance.

**Verification.** Check the order with results of known dates and scores,
including ties.

### RF07 · Paging of the results <a id="RF07"></a>

**Objective.** Go through an extensive set without losing the context.

**Expected behaviour.** Allow moving forward and back between pages, indicate
the current position and preserve expression, filters and ordering. Prevent
navigating beyond the first or the last page.

**Verification.** Go through several pages and return, checking position, scope
and stability of the results.

### RF08 · Coverage of the base <a id="RF08"></a>

**Objective.** Know the reach of the available data before using it.

**Expected behaviour.** Show the number of documents, the number of courts and
the period available. Compute the values from the searchable base and state
partial coverage or unavailable information.

**Verification.** Compare counts and dates with the available records, including
an empty base and partial coverage.

### RF09 · Evolution of the volume over time <a id="RF09"></a>

**Objective.** Observe how the number of decisions varies over the period.

**Expected behaviour.** Group the documents of the scope into identified time
intervals, stating the date used in the calculation. Allow opening the documents
of each interval and treat records without a date explicitly.

**Verification.** Compare each interval with its documents and check the sum of
the groups considered.

### RF10 · Proportion of appeal outcomes <a id="RF10"></a>

**Objective.** Observe the distribution between appeals granted, partially
granted and denied.

**Expected behaviour.** Present the categories and their proportions within the
scope, with an explicit basis of calculation. Identify records without a
classification, without presuming them denied. Allow opening the documents of
each category.

**Verification.** Check classifications, numerators and denominator against a
sample and against the totals of the scope.

### RF11 · Additional legal filters <a id="RF11"></a>

**Objective.** Narrow the search by judging body, reporting judge and procedural
class.

**Expected behaviour.** Offer filters fed by the data and combine them with
expression, court and period. Show the applied scope and update results and
total.

**Verification.** Apply each filter and their combinations and check that every
document matches the scope.

### RF12 · Documents behind the indicators <a id="RF12"></a>

**Objective.** Check the evidence that supports each number.

**Expected behaviour.** Allow opening the list of documents corresponding to an
indicator, preserving the scope and the selected condition. Make limitations or
estimates explicit where they exist.

**Verification.** Compare the set opened with the rule of calculation and the
total of the indicator.

### RF13 · Unanimity or majority <a id="RF13"></a>

**Objective.** Know the form of deliberation recorded in the decision.

**Expected behaviour.** State whether the decision was unanimous or by majority
when that information is available. Show a not-informed state in the remaining
cases, without deducing unanimity from the absence of dissent.

**Verification.** Check examples of unanimity, of majority and of absent
information against the origin.

### RF14 · Export of the scope <a id="RF14"></a>

**Objective.** Take the search to an external analysis with verifiable
references.

**Expected behaviour.** Export the scope with the filters applied and the
references of the documents. State the date of the export and the collection
dates available. The format and the limits of the export must be stated in the
criteria of the user story.

**Verification.** Open the file generated and check scope, references, dates and
the limits stated.

### RF15 · Comparison between courts <a id="RF15"></a>

**Objective.** Compare courts side by side on the same subject.

**Expected behaviour.** Apply the same expression, period and criteria to the
courts compared. Present equivalent metrics, supporting documents and
differences in coverage; distinguish absence of documents from unavailability of
the source.

**Verification.** Check each side against its equivalent search and test courts
with distinct coverage.

### RF16 · Status of the sources and last collection <a id="RF16"></a>

**Objective.** Know where the data comes from and when it was collected.

**Expected behaviour.** Show the status of each source and the date of the last
collection, distinguishing a completed collection from a failed attempt. State
unavailable sources and do not replace unknown dates with estimated values.

**Verification.** Compare the interface with the collection records in cases of
success, of failure and of absence of collection.

### RF17 · Saved search <a id="RF17"></a>

**Objective.** Resume a search with the filters already defined.

**Expected behaviour.** Keep the expression and the filters and allow reapplying
them. Saving a search does not imply freezing the documents found. Ownership,
sharing and persistence must be defined in the user story before
implementation.

**Verification.** Save and reopen a search, checking the restoration of the
expression and of the filters.

### RF18 · Concentration by judging body and reporting judge <a id="RF18"></a>

**Objective.** Identify where the searched set is concentrated.

**Expected behaviour.** Group the volume of the scope by judging body and by
reporting judge. Preserve the identification of the groups, treat absent values
and allow opening their documents. State the grouping rule when there is an
Other category.

**Verification.** Check groups and totals against the documents of the scope,
including records without metadata.

### RF19 · Laws, articles and precedents cited <a id="RF19"></a>

**Objective.** Consult the grounds referenced in the decision.

**Expected behaviour.** Show the references identified in the document, with
context that allows verifying the citation. Offer access to the origin where
available and identify unresolved references. Do not present a suggested
reference as if it had been cited.

**Verification.** Compare the references shown with the text of the decision and
check the destinations of the links.

### RF20 · Semantically close decisions <a id="RF20"></a>

**Objective.** Find other documents with content related to a decision.

**Expected behaviour.** Present close decisions and allow opening them. State
the origin or the method of the relation and distinguish official relations from
computed similarity. Semantic proximity does not prove identity of legal
understanding.

**Verification.** Validate a sample of relations, their documents and the
identification of the method used.

### RF21 · Report of an incorrect classification <a id="RF21"></a>

**Objective.** Report errors found during the search.

**Expected behaviour.** Allow reporting an incorrect classification, linking the
report to the document and to the information contested. Confirm receipt; the
report does not automatically change the classification published.

**Verification.** Send a report and check its record and the preservation of the
classification until review.

### RF22 · Divergences between panels <a id="RF22"></a>

**Objective.** Investigate differences of understanding within the same court.

**Expected behaviour.** Present indications of divergence with subject, panels,
period and the decisions that support the comparison. The criteria for
identifying divergence must be defined and validated in the user story; a
difference in volume alone does not prove legal divergence.

**Verification.** Check the cases identified against the decisions that support
them and against the rule approved for the comparison.

### RF23 · Decisions to the contrary <a id="RF23"></a>

**Objective.** Find documents that may contradict the understanding searched
for.

**Expected behaviour.** Show potentially contrary decisions, explaining the
context compared and the reason for the indication. Allow checking the
documents; the indication must be distinguished from a definitive legal
conclusion.

**Verification.** Validate a sample of results and their justification according
to the criteria defined in the user story.

---

## Quality requirements

They apply to the features affected. Numeric targets not defined in the proposal
must be agreed and recorded before being used as a condition of acceptance.

### RNF01 · Traceability <a id="RNF01"></a>

**Objective.** Preserve the relation between results, indicators and source
documents.

**Expected behaviour.** Each result keeps its source; indicators allow reaching
the documents and the scope used.

**Verification.** Walk from a result and from an indicator to the origin and
check filters and references.

### RNF02 · Security <a id="RNF02"></a>

**Objective.** Protect data, access and credentials.

**Expected behaviour.** Control the operations according to the permissions
foreseen; do not expose credentials in the code, in the interface or in the
execution records.

**Verification.** Review permissions, exposure of secrets and access to the
protected operations.

### RNF03 · Privacy <a id="RNF03"></a>

**Objective.** Treat judicial data according to the applicable rules.

**Expected behaviour.** Restrict the exposure of protected information and block
pre-emptively, for review, records suspected of judicial secrecy.

**Verification.** Test the block and check that restricted content does not
appear in results, details or exports.

### RNF04 · Performance <a id="RNF04"></a>

**Objective.** Answer the queries in a time adequate to interactive use.

**Expected behaviour.** Measure response time with the volume of data, the
queries and the environment identified. The proposal does not establish a
general numeric limit; specific targets belong to the corresponding user story.

**Verification.** Run reproducible measurements and compare them with the target
recorded for the feature.

### RNF05 · Scalability <a id="RNF05"></a>

**Objective.** Support the growth of the volume searched.

**Expected behaviour.** Evaluate search and processing as the base grows,
recording the limits of capacity and the resources used.

**Verification.** Run scenarios with growing volumes and record time,
consumption and the limits found.

### RNF06 · Availability <a id="RNF06"></a>

**Objective.** Prevent the unavailability of one source from interrupting the
whole application.

**Expected behaviour.** Isolate failures per source and state the
unavailability, keeping accessible the features and the data not affected.

**Verification.** Simulate the failure of one source and check the continuity of
the rest of the application.

### RNF07 · Data quality <a id="RNF07"></a>

**Objective.** Monitor completeness, uniqueness, validity and currency.

**Expected behaviour.** Identify absent fields, duplicates, invalid data and
staleness of the collections; record the treatment and the limitations relevant
to the user.

**Verification.** Apply checks over samples and totals and review the records of
the problems found.

### RNF08 · Observability <a id="RNF08"></a>

**Objective.** Record evidence of execution and of failure.

**Expected behaviour.** Keep records that allow identifying the operation, the
time, the outcome and the error, preserving credentials and restricted content.

**Verification.** Locate a successful execution and a failure in the records and
follow their diagnosis.

### RNF09 · Accessibility <a id="RNF09"></a>

**Objective.** Follow good practice in digital accessibility.

**Expected behaviour.** Offer keyboard navigation, visible focus,
understandable labels, contrast and messages that do not depend on colour
alone.

**Verification.** Check the main flows by keyboard and run checks of labels, of
contrast and of assistive reading.

### RNF10 · Maintainability <a id="RNF10"></a>

**Objective.** Keep the code tested, documented and organised.

**Expected behaviour.** Keep the instructions for running the project up to
date, the organisation consistent and the rules changed covered by tests, with
code review.

**Verification.** Run the checks of the project and review the documentation and
the review of the change.

---

## Change control

Record changes of definition in the requirement affected, with reason, date and
related user story. Preserve the ID and the history of the page.

Source: solution proposal, pages 2–3; the detail guides the refinement of the
user stories.
