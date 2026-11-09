-- Synthetic data for the agentgateway MCP governance reference implementation.
-- Every value here is fictional. National IDs use the never-issued 900 area,
-- phone numbers use the reserved 555-01xx range, and emails use example.com.
-- Generated deterministically; edit by hand with care (ledger balances must add up).

PRAGMA foreign_keys = ON;

CREATE TABLE customers (
    customer_id    TEXT PRIMARY KEY CHECK (customer_id GLOB 'CUST-[0-9][0-9][0-9][0-9]'),
    full_name      TEXT NOT NULL,
    email          TEXT NOT NULL,
    phone          TEXT NOT NULL,
    national_id    TEXT NOT NULL,
    date_of_birth  TEXT NOT NULL,
    risk_rating    TEXT NOT NULL CHECK (risk_rating IN ('low', 'medium', 'high')),
    created_at     TEXT NOT NULL
);

CREATE TABLE accounts (
    account_id      TEXT PRIMARY KEY CHECK (account_id GLOB 'ACC-[0-9][0-9][0-9][0-9]'),
    customer_id     TEXT NOT NULL REFERENCES customers (customer_id),
    account_number  TEXT NOT NULL UNIQUE,
    account_type    TEXT NOT NULL CHECK (account_type IN ('checking', 'savings', 'business')),
    currency        TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('active', 'frozen', 'under_review')),
    opened_at       TEXT NOT NULL
);

CREATE TABLE transactions (
    transaction_id  TEXT PRIMARY KEY CHECK (transaction_id GLOB 'TXN-[0-9][0-9][0-9][0-9][0-9][0-9]'),
    account_id      TEXT NOT NULL REFERENCES accounts (account_id),
    direction       TEXT NOT NULL CHECK (direction IN ('credit', 'debit')),
    amount_cents    INTEGER NOT NULL CHECK (amount_cents > 0),
    currency        TEXT NOT NULL,
    counterparty    TEXT NOT NULL,
    description     TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('posted', 'pending', 'reversed')),
    posted_at       TEXT NOT NULL
);

CREATE TABLE ledger_entries (
    entry_id             TEXT PRIMARY KEY CHECK (entry_id GLOB 'LED-[0-9][0-9][0-9][0-9][0-9][0-9]'),
    account_id           TEXT NOT NULL REFERENCES accounts (account_id),
    transaction_id       TEXT NOT NULL UNIQUE REFERENCES transactions (transaction_id),
    entry_type           TEXT NOT NULL CHECK (entry_type IN ('credit', 'debit')),
    amount_cents         INTEGER NOT NULL CHECK (amount_cents > 0),
    balance_after_cents  INTEGER NOT NULL,
    posted_at            TEXT NOT NULL
);

CREATE INDEX idx_accounts_customer ON accounts (customer_id);
CREATE INDEX idx_transactions_account ON transactions (account_id, posted_at);
CREATE INDEX idx_ledger_account ON ledger_entries (account_id, posted_at);

INSERT INTO customers (customer_id, full_name, email, phone, national_id, date_of_birth, risk_rating, created_at) VALUES
    ('CUST-0001', 'Amara Okafor', 'amara.okafor@example.com', '+1-555-0101', '900-12-3401', '1984-03-12', 'low', '2024-01-15T09:00:00Z'),
    ('CUST-0002', 'Daniel Mekonnen', 'daniel.mekonnen@example.com', '+1-555-0102', '900-12-3402', '1979-11-02', 'medium', '2024-02-15T09:00:00Z'),
    ('CUST-0003', 'Lucia Fernandez', 'lucia.fernandez@example.com', '+1-555-0103', '900-12-3403', '1991-07-23', 'high', '2024-03-15T09:00:00Z'),
    ('CUST-0004', 'Kenji Watanabe', 'kenji.watanabe@example.com', '+1-555-0104', '900-12-3404', '1968-01-30', 'low', '2024-04-15T09:00:00Z'),
    ('CUST-0005', 'Sara Haile', 'sara.haile@example.com', '+1-555-0105', '900-12-3405', '1995-05-17', 'medium', '2024-05-15T09:00:00Z');

INSERT INTO accounts (account_id, customer_id, account_number, account_type, currency, status, opened_at) VALUES
    ('ACC-1001', 'CUST-0001', '400034651979', 'checking', 'USD', 'active', '2024-01-20T10:00:00Z'),
    ('ACC-1002', 'CUST-0001', '400016389657', 'savings', 'USD', 'active', '2024-02-20T10:00:00Z'),
    ('ACC-1003', 'CUST-0002', '400075741193', 'checking', 'USD', 'active', '2024-03-20T10:00:00Z'),
    ('ACC-1004', 'CUST-0003', '400048943013', 'checking', 'USD', 'active', '2024-04-20T10:00:00Z'),
    ('ACC-1005', 'CUST-0003', '400093094116', 'business', 'USD', 'under_review', '2024-05-20T10:00:00Z'),
    ('ACC-1006', 'CUST-0004', '400028526687', 'checking', 'USD', 'active', '2024-06-20T10:00:00Z'),
    ('ACC-1007', 'CUST-0005', '400066929186', 'savings', 'USD', 'frozen', '2024-07-20T10:00:00Z');

INSERT INTO transactions (transaction_id, account_id, direction, amount_cents, currency, counterparty, description, status, posted_at) VALUES
    ('TXN-000001', 'ACC-1001', 'credit', 341213, 'USD', 'Opening Deposit', 'Opening deposit', 'posted', '2026-09-04T19:25:00Z'),
    ('TXN-000002', 'ACC-1001', 'debit', 14941, 'USD', 'Northwind Grocers', 'Card payment to Northwind Grocers', 'posted', '2026-09-06T05:02:00Z'),
    ('TXN-000003', 'ACC-1001', 'debit', 56418, 'USD', 'Tailspin Airlines', 'Card payment to Tailspin Airlines', 'posted', '2026-09-09T18:28:00Z'),
    ('TXN-000004', 'ACC-1001', 'credit', 178597, 'USD', 'Fabrikam Payroll', 'Salary payment', 'posted', '2026-09-13T18:17:00Z'),
    ('TXN-000005', 'ACC-1001', 'debit', 25785, 'USD', 'Contoso Utilities', 'Card payment to Contoso Utilities', 'posted', '2026-09-14T11:29:00Z'),
    ('TXN-000006', 'ACC-1002', 'credit', 881132, 'USD', 'Opening Deposit', 'Opening deposit', 'posted', '2026-09-05T18:05:00Z'),
    ('TXN-000007', 'ACC-1002', 'credit', 258104, 'USD', 'Fabrikam Payroll', 'Salary payment', 'posted', '2026-09-06T07:14:00Z'),
    ('TXN-000008', 'ACC-1002', 'credit', 185921, 'USD', 'Fabrikam Payroll', 'Salary payment', 'posted', '2026-09-09T20:13:00Z'),
    ('TXN-000009', 'ACC-1002', 'debit', 51718, 'USD', 'Adventure Works Retail', 'Card payment to Adventure Works Retail', 'posted', '2026-09-13T17:28:00Z'),
    ('TXN-000010', 'ACC-1002', 'credit', 93410, 'USD', 'Fabrikam Payroll', 'Salary payment', 'posted', '2026-09-14T06:52:00Z'),
    ('TXN-000011', 'ACC-1002', 'debit', 23285, 'USD', 'Contoso Utilities', 'Card payment to Contoso Utilities', 'posted', '2026-09-15T21:07:00Z'),
    ('TXN-000012', 'ACC-1003', 'credit', 724974, 'USD', 'Opening Deposit', 'Opening deposit', 'posted', '2026-09-03T10:04:00Z'),
    ('TXN-000013', 'ACC-1003', 'credit', 288868, 'USD', 'Fabrikam Payroll', 'Salary payment', 'posted', '2026-09-04T06:07:00Z'),
    ('TXN-000014', 'ACC-1003', 'debit', 30959, 'USD', 'Litware Insurance', 'Card payment to Litware Insurance', 'posted', '2026-09-06T15:15:00Z'),
    ('TXN-000015', 'ACC-1003', 'debit', 45808, 'USD', 'Proseware Rent', 'Card payment to Proseware Rent', 'posted', '2026-09-07T05:42:00Z'),
    ('TXN-000016', 'ACC-1003', 'debit', 30960, 'USD', 'Northwind Grocers', 'Card payment to Northwind Grocers', 'posted', '2026-09-08T02:26:00Z'),
    ('TXN-000017', 'ACC-1003', 'debit', 17757, 'USD', 'Northwind Grocers', 'Card payment to Northwind Grocers', 'posted', '2026-09-09T08:26:00Z'),
    ('TXN-000018', 'ACC-1003', 'credit', 43740, 'USD', 'Fabrikam Payroll', 'Salary payment', 'posted', '2026-09-11T05:17:00Z'),
    ('TXN-000019', 'ACC-1004', 'credit', 655264, 'USD', 'Opening Deposit', 'Opening deposit', 'posted', '2026-09-05T17:10:00Z'),
    ('TXN-000020', 'ACC-1004', 'debit', 29429, 'USD', 'Wide World Importers', 'Card payment to Wide World Importers', 'posted', '2026-09-07T17:12:00Z'),
    ('TXN-000021', 'ACC-1004', 'debit', 55312, 'USD', 'Proseware Rent', 'Card payment to Proseware Rent', 'posted', '2026-09-08T03:46:00Z'),
    ('TXN-000022', 'ACC-1004', 'debit', 59071, 'USD', 'Tailspin Airlines', 'Card payment to Tailspin Airlines', 'posted', '2026-09-12T01:28:00Z'),
    ('TXN-000023', 'ACC-1004', 'credit', 282954, 'USD', 'Fabrikam Payroll', 'Salary payment', 'posted', '2026-09-14T05:46:00Z'),
    ('TXN-000024', 'ACC-1004', 'credit', 175717, 'USD', 'Fabrikam Payroll', 'Salary payment', 'posted', '2026-09-16T00:09:00Z'),
    ('TXN-000025', 'ACC-1005', 'credit', 829802, 'USD', 'Opening Deposit', 'Opening deposit', 'posted', '2026-09-02T05:27:00Z'),
    ('TXN-000026', 'ACC-1005', 'debit', 56960, 'USD', 'Litware Insurance', 'Card payment to Litware Insurance', 'posted', '2026-09-03T11:31:00Z'),
    ('TXN-000027', 'ACC-1005', 'debit', 24804, 'USD', 'Contoso Utilities', 'Card payment to Contoso Utilities', 'posted', '2026-09-06T15:53:00Z'),
    ('TXN-000028', 'ACC-1005', 'debit', 29025, 'USD', 'Proseware Rent', 'Card payment to Proseware Rent', 'posted', '2026-09-08T23:43:00Z'),
    ('TXN-000029', 'ACC-1005', 'credit', 48285, 'USD', 'Fabrikam Payroll', 'Salary payment', 'posted', '2026-09-12T01:34:00Z'),
    ('TXN-000030', 'ACC-1005', 'debit', 16201, 'USD', 'Tailspin Airlines', 'Card payment to Tailspin Airlines', 'posted', '2026-09-15T09:24:00Z'),
    ('TXN-000031', 'ACC-1006', 'credit', 555865, 'USD', 'Opening Deposit', 'Opening deposit', 'posted', '2026-09-03T04:31:00Z'),
    ('TXN-000032', 'ACC-1006', 'debit', 22340, 'USD', 'Tailspin Airlines', 'Card payment to Tailspin Airlines', 'posted', '2026-09-06T13:19:00Z'),
    ('TXN-000033', 'ACC-1006', 'debit', 59327, 'USD', 'Litware Insurance', 'Card payment to Litware Insurance', 'posted', '2026-09-09T12:43:00Z'),
    ('TXN-000034', 'ACC-1006', 'debit', 39580, 'USD', 'Contoso Utilities', 'Card payment to Contoso Utilities', 'posted', '2026-09-12T17:11:00Z'),
    ('TXN-000035', 'ACC-1006', 'credit', 147020, 'USD', 'Fabrikam Payroll', 'Salary payment', 'posted', '2026-09-13T02:50:00Z'),
    ('TXN-000036', 'ACC-1006', 'debit', 17883, 'USD', 'Litware Insurance', 'Card payment to Litware Insurance', 'posted', '2026-09-15T01:48:00Z'),
    ('TXN-000037', 'ACC-1007', 'credit', 638029, 'USD', 'Opening Deposit', 'Opening deposit', 'posted', '2026-09-04T08:55:00Z'),
    ('TXN-000038', 'ACC-1007', 'debit', 57449, 'USD', 'Proseware Rent', 'Card payment to Proseware Rent', 'posted', '2026-09-07T08:31:00Z'),
    ('TXN-000039', 'ACC-1007', 'debit', 32371, 'USD', 'Litware Insurance', 'Card payment to Litware Insurance', 'posted', '2026-09-10T00:56:00Z'),
    ('TXN-000040', 'ACC-1007', 'debit', 49960, 'USD', 'Northwind Grocers', 'Card payment to Northwind Grocers', 'posted', '2026-09-10T11:39:00Z'),
    ('TXN-000041', 'ACC-1007', 'debit', 56080, 'USD', 'Litware Insurance', 'Card payment to Litware Insurance', 'posted', '2026-09-12T20:17:00Z'),
    ('TXN-000042', 'ACC-1007', 'credit', 129957, 'USD', 'Fabrikam Payroll', 'Salary payment', 'posted', '2026-09-14T08:39:00Z'),
    ('TXN-000043', 'ACC-1007', 'credit', 86669, 'USD', 'Fabrikam Payroll', 'Salary payment', 'posted', '2026-09-14T18:57:00Z');

INSERT INTO ledger_entries (entry_id, account_id, transaction_id, entry_type, amount_cents, balance_after_cents, posted_at) VALUES
    ('LED-000001', 'ACC-1001', 'TXN-000001', 'credit', 341213, 341213, '2026-09-04T19:25:00Z'),
    ('LED-000002', 'ACC-1001', 'TXN-000002', 'debit', 14941, 326272, '2026-09-06T05:02:00Z'),
    ('LED-000003', 'ACC-1001', 'TXN-000003', 'debit', 56418, 269854, '2026-09-09T18:28:00Z'),
    ('LED-000004', 'ACC-1001', 'TXN-000004', 'credit', 178597, 448451, '2026-09-13T18:17:00Z'),
    ('LED-000005', 'ACC-1001', 'TXN-000005', 'debit', 25785, 422666, '2026-09-14T11:29:00Z'),
    ('LED-000006', 'ACC-1002', 'TXN-000006', 'credit', 881132, 881132, '2026-09-05T18:05:00Z'),
    ('LED-000007', 'ACC-1002', 'TXN-000007', 'credit', 258104, 1139236, '2026-09-06T07:14:00Z'),
    ('LED-000008', 'ACC-1002', 'TXN-000008', 'credit', 185921, 1325157, '2026-09-09T20:13:00Z'),
    ('LED-000009', 'ACC-1002', 'TXN-000009', 'debit', 51718, 1273439, '2026-09-13T17:28:00Z'),
    ('LED-000010', 'ACC-1002', 'TXN-000010', 'credit', 93410, 1366849, '2026-09-14T06:52:00Z'),
    ('LED-000011', 'ACC-1002', 'TXN-000011', 'debit', 23285, 1343564, '2026-09-15T21:07:00Z'),
    ('LED-000012', 'ACC-1003', 'TXN-000012', 'credit', 724974, 724974, '2026-09-03T10:04:00Z'),
    ('LED-000013', 'ACC-1003', 'TXN-000013', 'credit', 288868, 1013842, '2026-09-04T06:07:00Z'),
    ('LED-000014', 'ACC-1003', 'TXN-000014', 'debit', 30959, 982883, '2026-09-06T15:15:00Z'),
    ('LED-000015', 'ACC-1003', 'TXN-000015', 'debit', 45808, 937075, '2026-09-07T05:42:00Z'),
    ('LED-000016', 'ACC-1003', 'TXN-000016', 'debit', 30960, 906115, '2026-09-08T02:26:00Z'),
    ('LED-000017', 'ACC-1003', 'TXN-000017', 'debit', 17757, 888358, '2026-09-09T08:26:00Z'),
    ('LED-000018', 'ACC-1003', 'TXN-000018', 'credit', 43740, 932098, '2026-09-11T05:17:00Z'),
    ('LED-000019', 'ACC-1004', 'TXN-000019', 'credit', 655264, 655264, '2026-09-05T17:10:00Z'),
    ('LED-000020', 'ACC-1004', 'TXN-000020', 'debit', 29429, 625835, '2026-09-07T17:12:00Z'),
    ('LED-000021', 'ACC-1004', 'TXN-000021', 'debit', 55312, 570523, '2026-09-08T03:46:00Z'),
    ('LED-000022', 'ACC-1004', 'TXN-000022', 'debit', 59071, 511452, '2026-09-12T01:28:00Z'),
    ('LED-000023', 'ACC-1004', 'TXN-000023', 'credit', 282954, 794406, '2026-09-14T05:46:00Z'),
    ('LED-000024', 'ACC-1004', 'TXN-000024', 'credit', 175717, 970123, '2026-09-16T00:09:00Z'),
    ('LED-000025', 'ACC-1005', 'TXN-000025', 'credit', 829802, 829802, '2026-09-02T05:27:00Z'),
    ('LED-000026', 'ACC-1005', 'TXN-000026', 'debit', 56960, 772842, '2026-09-03T11:31:00Z'),
    ('LED-000027', 'ACC-1005', 'TXN-000027', 'debit', 24804, 748038, '2026-09-06T15:53:00Z'),
    ('LED-000028', 'ACC-1005', 'TXN-000028', 'debit', 29025, 719013, '2026-09-08T23:43:00Z'),
    ('LED-000029', 'ACC-1005', 'TXN-000029', 'credit', 48285, 767298, '2026-09-12T01:34:00Z'),
    ('LED-000030', 'ACC-1005', 'TXN-000030', 'debit', 16201, 751097, '2026-09-15T09:24:00Z'),
    ('LED-000031', 'ACC-1006', 'TXN-000031', 'credit', 555865, 555865, '2026-09-03T04:31:00Z'),
    ('LED-000032', 'ACC-1006', 'TXN-000032', 'debit', 22340, 533525, '2026-09-06T13:19:00Z'),
    ('LED-000033', 'ACC-1006', 'TXN-000033', 'debit', 59327, 474198, '2026-09-09T12:43:00Z'),
    ('LED-000034', 'ACC-1006', 'TXN-000034', 'debit', 39580, 434618, '2026-09-12T17:11:00Z'),
    ('LED-000035', 'ACC-1006', 'TXN-000035', 'credit', 147020, 581638, '2026-09-13T02:50:00Z'),
    ('LED-000036', 'ACC-1006', 'TXN-000036', 'debit', 17883, 563755, '2026-09-15T01:48:00Z'),
    ('LED-000037', 'ACC-1007', 'TXN-000037', 'credit', 638029, 638029, '2026-09-04T08:55:00Z'),
    ('LED-000038', 'ACC-1007', 'TXN-000038', 'debit', 57449, 580580, '2026-09-07T08:31:00Z'),
    ('LED-000039', 'ACC-1007', 'TXN-000039', 'debit', 32371, 548209, '2026-09-10T00:56:00Z'),
    ('LED-000040', 'ACC-1007', 'TXN-000040', 'debit', 49960, 498249, '2026-09-10T11:39:00Z'),
    ('LED-000041', 'ACC-1007', 'TXN-000041', 'debit', 56080, 442169, '2026-09-12T20:17:00Z'),
    ('LED-000042', 'ACC-1007', 'TXN-000042', 'credit', 129957, 572126, '2026-09-14T08:39:00Z'),
    ('LED-000043', 'ACC-1007', 'TXN-000043', 'credit', 86669, 658795, '2026-09-14T18:57:00Z');
