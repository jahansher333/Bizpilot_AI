import { Page } from '@playwright/test';

export const TEST_ORG_ID = '01a0e000-0000-7000-8000-000000000001';
export const TEST_ORG_B_ID = '01a0e000-0000-7000-8000-000000000002';
export const TEST_USER_ID = '01a0e000-0000-7000-8000-000000000010';

export async function setupMockApi(page: Page, role: 'owner' | 'manager' | 'staff' = 'owner') {
  // Signed-in session: the app restores it on load by exchanging the stored refresh token
  // (FIX-008 workspace route guard sends signed-out visitors to /login).
  await page.addInitScript(() => {
    window.localStorage.setItem('bizpilot_refresh_token', 'e2e-refresh-token');
  });
  await page.route('**/api/auth/refresh', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'e2e-access-token',
        refresh_token: 'e2e-refresh-token',
        token_type: 'bearer',
        expires_in: 900,
      }),
    });
  });

  // Mock auth check / user
  await page.route('**/api/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: TEST_USER_ID,
        email: 'owner@lahorestore.pk',
        display_name: 'Haji Muhammad',
        role,
      }),
    });
  });

  // Mock organizations list
  await page.route('**/api/organizations', async (route) => {
    if (route.request().method() === 'POST') {
      const data = route.request().postDataJSON();
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: TEST_ORG_ID,
          display_name: data.display_name || 'Lahore Super Store',
          currency_code: 'PKR',
          timezone: 'Asia/Karachi',
          role: 'owner',
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: TEST_ORG_ID,
          display_name: 'Lahore Super Store',
          currency_code: 'PKR',
          timezone: 'Asia/Karachi',
          role,
        },
      ]),
    });
  });

  // Mock organization details
  await page.route(`**/api/organizations/${TEST_ORG_ID}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: TEST_ORG_ID,
        display_name: 'Lahore Super Store',
        currency_code: 'PKR',
        timezone: 'Asia/Karachi',
        role,
      }),
    });
  });

  // Mock Team members (Owner-only on the backend)
  await page.route(`**/api/organizations/${TEST_ORG_ID}/members*`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { id: 'm-1', organization_id: TEST_ORG_ID, user_id: TEST_USER_ID, role: 'owner', status: 'active', created_at: '2026-09-28T00:00:00Z', email: 'owner@lahorestore.pk', display_name: 'Haji Muhammad' },
        { id: 'm-2', organization_id: TEST_ORG_ID, user_id: 'u-2', role: 'staff', status: 'active', created_at: '2026-09-30T00:00:00Z', email: 'counter@lahorestore.pk', display_name: 'Bilal Counter' },
      ]),
    });
  });

  // Mock Dashboard (DashboardSummary shape; Staff gets no expenses or net cash)
  await page.route(`**/api/organizations/${TEST_ORG_ID}/dashboard*`, async (route) => {
    const today = new Date().toISOString().slice(0, 10);
    const restricted = role === 'staff';
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        sales: { order_count: 3, total_sales_minor: 1500000, currency_code: 'PKR' },
        payments: { payment_count: 2, total_collected_minor: 1000000, currency_code: 'PKR' },
        expenses: restricted ? null : { expense_count: 1, total_expenses_minor: 200000, currency_code: 'PKR' },
        net_cash: restricted ? null : { net_cash_minor: 800000, currency_code: 'PKR' },
        inventory: { low_stock_count: 0, low_stock_threshold: 10, items: [] },
        recent_activity: [],
        freshness: { generated_at: new Date().toISOString(), period: 'today', local_start_date: today, local_end_date: today, timezone: 'Asia/Karachi' },
      }),
    });
  });

  // Mock Categories
  await page.route(`**/api/organizations/${TEST_ORG_ID}/categories*`, async (route) => {
    if (route.request().method() === 'POST') {
      const data = route.request().postDataJSON();
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'cat-01', name: data.name }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [{ id: 'cat-01', name: 'Dry Fruits', status: 'active' }], total: 1, limit: 100, offset: 0 }),
    });
  });

  // Mock Products
  await page.route(`**/api/organizations/${TEST_ORG_ID}/products*`, async (route) => {
    if (route.request().method() === 'POST') {
      const data = route.request().postDataJSON();
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'prod-01',
          code: data.code || 'SKU-01',
          name: data.name,
          base_unit: data.base_unit || 'piece',
          default_price_minor: data.default_price_minor || 150000,
          category_id: data.category_id || 'cat-01',
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            id: 'prod-01',
            code: 'ALMOND-01',
            name: 'Kagzi Badam 1kg',
            base_unit: 'pack',
            default_price_minor: 150000,
            currency_code: 'PKR',
            status: 'active',
            category_id: 'cat-01',
          },
        ],
        total: 1,
      }),
    });
  });

  // Mock Inventory Balances
  await page.route(`**/api/organizations/${TEST_ORG_ID}/inventory/balances*`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            product_id: 'prod-01',
            product_name: 'Kagzi Badam 1kg',
            product_code: 'ALMOND-01',
            on_hand_quantity: 40,
            reorder_point: 10,
          },
        ],
        total: 1,
      }),
    });
  });

  // Mock Customers
  await page.route(`**/api/organizations/${TEST_ORG_ID}/customers*`, async (route) => {
    if (route.request().method() === 'POST') {
      const data = route.request().postDataJSON();
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'cust-01',
          name: data.name,
          phone: data.phone || '03001234567',
          balance_minor: 0,
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            id: 'cust-01',
            name: 'Al-Madina Traders',
            phone: '03001234567',
            balance_minor: 500000,
          },
        ],
        total: 1,
      }),
    });
  });

  // Mock Orders
  await page.route(`**/api/organizations/${TEST_ORG_ID}/orders*`, async (route) => {
    if (route.request().method() === 'POST') {
      const data = route.request().postDataJSON();
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'order-02',
          order_number: 'ORD-0042',
          customer_id: data.customer_id ?? null,
          ordered_at: new Date().toISOString(),
          order_total_minor: 150000,
          currency_code: 'PKR',
          status: 'active',
          items: [],
          created_at: new Date().toISOString(),
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            id: 'order-01',
            order_number: 'ORD-0001',
            customer_id: null,
            ordered_at: new Date().toISOString(),
            order_total_minor: 1500000,
            currency_code: 'PKR',
            status: 'active',
            items: [],
            created_at: new Date().toISOString(),
          },
        ],
        total: 1,
      }),
    });
  });

  // Mock Payments
  await page.route(`**/api/organizations/${TEST_ORG_ID}/payments*`, async (route) => {
    if (route.request().method() === 'POST') {
      const data = route.request().postDataJSON();
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'pay-01',
          amount_minor: data.amount_minor,
          channel: data.channel,
          customer_id: data.customer_id,
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            id: 'pay-01',
            payment_number: 'PAY-0001',
            amount_minor: 1000000,
            channel: 'bank_transfer',
            customer_id: null,
            order_id: null,
            received_at: new Date().toISOString(),
            status: 'active',
            currency_code: 'PKR',
            created_at: new Date().toISOString(),
          },
        ],
        total: 1,
      }),
    });
  });

  // Mock Expenses
  await page.route(`**/api/organizations/${TEST_ORG_ID}/expenses*`, async (route) => {
    if (role === 'staff') {
      await route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Forbidden: Insufficient role permissions' }),
      });
      return;
    }

    if (route.request().method() === 'POST') {
      const data = route.request().postDataJSON();
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'exp-01',
          amount_minor: data.amount_minor,
          payee: data.payee,
          payment_method: data.payment_method,
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            id: 'exp-01',
            amount_minor: 200000,
            payee: 'Lahore Goods Transport',
            payment_method: 'cash',
            expense_category_id: null,
            occurred_at: new Date().toISOString(),
            status: 'active',
            currency_code: 'PKR',
            created_at: new Date().toISOString(),
          },
        ],
        total: 1,
      }),
    });
  });

  // Mock AI Assistant chat
  await page.route(`**/api/organizations/${TEST_ORG_ID}/ai/chat*`, async (route) => {
    const data = route.request().postDataJSON();
    const query = (data?.message || '').toLowerCase();

    if (query.includes('sales') || query.includes('today')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          content: "Today's total sales are PKR 15,000.00 across 3 confirmed orders.",
          model: 'gpt-4o-mini',
          latency_ms: 120.5,
          tool_calls: [{ tool_name: 'get_sales_summary', status: 'success' }],
          provenance: [
            { source_tool: 'get_sales_summary', period_applied: 'today', calculation_method: 'deterministic_service' },
          ],
        }),
      });
      return;
    }

    if (query.includes('create') || query.includes('order') || query.includes('modify')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          content: 'BizPilot AI is strictly a read-only assistant. Please record orders directly using the Orders screen.',
          model: 'gpt-4o-mini',
          latency_ms: 85.0,
          tool_calls: [],
          provenance: [],
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        content: 'I am your BizPilot AI business assistant. How can I help you inspect your sales, inventory, or balances?',
        model: 'gpt-4o-mini',
        latency_ms: 95.0,
        tool_calls: [],
        provenance: [],
      }),
    });
  });
}
