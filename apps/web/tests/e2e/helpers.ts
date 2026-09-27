import { Page } from '@playwright/test';

export const TEST_ORG_ID = '01a0e000-0000-7000-8000-000000000001';
export const TEST_ORG_B_ID = '01a0e000-0000-7000-8000-000000000002';
export const TEST_USER_ID = '01a0e000-0000-7000-8000-000000000010';

export async function setupMockApi(page: Page, role: 'owner' | 'manager' | 'staff' = 'owner') {
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

  // Mock Dashboard
  await page.route(`**/api/organizations/${TEST_ORG_ID}/dashboard*`, async (route) => {
    if (role === 'staff') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          sales: { total_sales_minor: 1500000, total_sales_pkr: '15,000.00', order_count: 3 },
          payments: { total_collected_minor: 1000000, total_collected_pkr: '10,000.00', payment_count: 2 },
          expenses: null,
          net_cash: null,
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        sales: { total_sales_minor: 1500000, total_sales_pkr: '15,000.00', order_count: 3 },
        payments: { total_collected_minor: 1000000, total_collected_pkr: '10,000.00', payment_count: 2 },
        expenses: { total_expenses_minor: 200000, total_expenses_pkr: '2,000.00', expense_count: 1 },
        net_cash: { net_cash_minor: 800000, net_cash_pkr: '8,000.00', status: 'positive' },
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
      body: JSON.stringify([{ id: 'cat-01', name: 'Dry Fruits' }]),
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
          id: 'order-01',
          customer_id: data.customer_id,
          order_total_minor: 1500000,
          status: 'confirmed',
          items: data.items,
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
            customer_name: 'Al-Madina Traders',
            order_total_minor: 1500000,
            status: 'confirmed',
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
            amount_minor: 1000000,
            channel: 'bank_transfer',
            customer_name: 'Al-Madina Traders',
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
