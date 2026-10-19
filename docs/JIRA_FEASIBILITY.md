# Jira API feasibility

Reviewed October 19, 2026 against official Atlassian Cloud documentation. The replacement v2 token passes live identity, Platform, and JSM reads. The authorized internal comment write, separate read-back, and persistent duplicate prevention pass. Documented API availability is separate from account-specific access. See [measured results](RESULTS.md).

## Endpoint map

Paths are relative to the site for unscoped Basic-auth tokens, or the gateway prefix for scoped tokens. Initial utility uses email/token Basic authentication as documented for personal scripts. OAuth 3LO remains an adoption consideration. [Authentication reference](https://developer.atlassian.com/cloud/jira/platform/basic-auth-for-rest-apis/), [scoped token routing](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/).

| Purpose | Endpoint | Use in AccessFlow |
| --- | --- | --- |
| Authenticated identity | `GET /rest/api/3/myself` | Require active account ID; omit profile from report |
| Project inventory | `GET /rest/api/3/project/search` | Paginated accessible metadata |
| Desk inventory/detail | `GET /rest/servicedeskapi/servicedesk` and `/{id}` | Match actual project key/ID |
| Request types | `GET /rest/servicedeskapi/servicedesk/{id}/requesttype` | Discover allowlisted desk configuration |
| Required request fields | `GET /rest/servicedeskapi/servicedesk/{id}/requesttype/{typeId}/field` | Record `fieldId`, schema, required flag |
| Customer requests | `GET /rest/servicedeskapi/request` and `/{issueIdOrKey}` | Designated request now; ingestion later |
| Project verification | `GET /rest/api/3/issue/{issueIdOrKey}?fields=project,status` | Validate real project, canonical key, stable ID |
| Effective issue permissions | `GET /rest/api/3/mypermissions?issueId=...&permissions=...` | Report Browse, Comment, Edit, Transition, Assign |
| Editable fields | `GET /rest/api/3/issue/{id}/editmeta` | Discover permitted edits; no field edits yet |
| Update fields | `PUT /rest/api/3/issue/{id}` | Future configured labels/fields |
| Agent transitions | `GET/POST /rest/api/3/issue/{id}/transitions` | Discover now; configured transitions later |
| Comments | `GET/POST /rest/servicedeskapi/request/{id}/comment` | Connectivity probe, exact-approved triage, and separately bounded worker triage; current worker writes disabled |
| Verify comment | `GET /rest/servicedeskapi/request/{id}/comment/{commentId}` | Verify body, author, visibility |
| Native approval records | `GET /rest/servicedeskapi/request/{id}/approval` | Read only; never answer approvals |

Endpoint references: [Myself](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-myself/), [Projects](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-projects/), [Service desk and request fields](https://developer.atlassian.com/cloud/jira/service-desk/rest/api-group-servicedesk/), [Requests, comments, and approvals](https://developer.atlassian.com/cloud/jira/service-desk/rest/api-group-request/), [Permissions](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-permissions/), [Issue edits and transitions](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/).

## Constraints that affect the design

- JSM `public: false` is an internal comment; `public: true` is customer-visible. Customers can create public comments only; agents can view internal comments. Require explicit visibility and verify it after writing. Add Comments and request access are required. [Comment API](https://developer.atlassian.com/cloud/jira/service-desk/rest/api-group-request/#api-rest-servicedeskapi-request-issueidorkey-comment-post).
- Request-list visibility depends on the caller. A customer sees their own/participating requests; the intended worker must be validated with an agent identity. Request fields and transitions vary by configuration. [JSM API](https://developer.atlassian.com/cloud/jira/service-desk/rest/api-group-request/).
- Field edits require applicable browse/edit permissions; transitions are a separate operation with workflow conditions. Never assume a status name, custom field ID, or transition ID. Assignment requires separate permission. [Issue API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/).
- Current polling classifies requests and can append an explicitly authorized internal next-action comment. It does not change fields/status/assignment or move requests into queues. Any later routing would need validated field/workflow configuration and separate authorization. [Queue overview](https://support.atlassian.com/jira-service-management-cloud/docs/what-are-queues/).
- Approval records are genuine JSM workflow records. A successful read with no records says nothing conclusive about configured approval steps. Project type, plan, and workflow must be checked separately. [Approval setup](https://support.atlassian.com/jira-service-management-cloud/docs/set-up-approvals/).
- Free accounts have permission/security configuration restrictions. The actual plan is unknown; advanced approval or workflow customization is not promised. [Free-plan restrictions](https://confluence.atlassian.com/servicedeskcloud/project-permissions-roles-and-issue-level-security-in-free-plans-1097175961.html).
- GET requests retry bounded transient failures with backoff and `Retry-After`. POST comments are never automatically resent after uncertain responses. [Rate limiting](https://developer.atlassian.com/cloud/jira/platform/rate-limiting/).

## Account capability evidence to collect

| Check | Current evidence |
| --- | --- |
| Active identity and real API authentication | Verified with replacement v2 token through the scoped gateway |
| Accessible service project and desk | AIS project 10001, service desk 2 verified |
| Request types, required fields, editable fields | Request admin access type 10 and field metadata verified |
| Effective issue permissions and transitions | Browse/Comment/Edit/Transition/Assign reported true; transitions discovered; none executed |
| Internal/public comment visibility | Exact INTERNAL comment verified with `public: false`; public comments not tested |
| Verified comment round trip | Comment 10003 created and read back; same-process and fresh-process repeats returned the same ID with one matching comment |
| Subscription and workflow approval steps | User/admin confirmation needed |
| Real approval decision observed | Not attempted |

Milestones 1 and 2 pass within the CLI/comment scope. Milestone 3 additionally verified automatic discovery, one separately authorized AIS-5 internal comment 10007, independent read-back and native worker restart without additional POSTs. Writes are disabled. See [actual evidence](RESULTS.md) and [final verification](FINAL_VERIFICATION.md). Subscription/native approval configuration, Docker execution and production rollout remain unverified.
