# SQL Server Schema: SAMPLE_DB

Exported at (UTC): 2026-10-16T04:48:46+00:00

Tables: 3; Views: 1; Fields: 22

Field names are complete; their order follows SQL Server column_id.

## T [dbo].[Bond] (6 fields)

| Ordinal | Field name |
|---:|---|
| 1 | [BondID] |
| 2 | [DealID] |
| 3 | [BondClass] |
| 4 | [CUSIP] |
| 5 | [CouponRate] |
| 6 | [MaturityDate] |

## T [dbo].[Deal] (6 fields)

| Ordinal | Field name |
|---:|---|
| 1 | [DealID] |
| 2 | [DealName] |
| 3 | [AssetTypeCode] |
| 4 | [ReportingDate] |
| 5 | [OriginalBalance] |
| 6 | [CreatedDate] |

## V [dbo].[vw_DealSummary] (4 fields)

| Ordinal | Field name |
|---:|---|
| 1 | [DealID] |
| 2 | [DealName] |
| 3 | [BondCount] |
| 4 | [TotalBalance] |

## T [report].[Asset] (6 fields)

| Ordinal | Field name |
|---:|---|
| 1 | [AssetID] |
| 2 | [DealID] |
| 3 | [PrincipalBalance] |
| 4 | [PaymentStatus] |
| 5 | [CurrentInterestRate] |
| 6 | [MaturityDate] |

