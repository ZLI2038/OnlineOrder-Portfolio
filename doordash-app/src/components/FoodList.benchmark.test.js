import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { Simulate } from 'react-dom/test-utils';
import FoodList from './FoodList';
import BaselineFoodList from '../__benchmarks__/BaselineFoodList';

const http = require('http');
const fs = require('fs');
const path = require('path');
let mockPort;
let mockRequests = [];
const mockPending = new Set();

function mockFetchJSON(url) {
  const promise = new Promise((resolve, reject) => {
    const request = http.get({ hostname: '127.0.0.1', port: mockPort, path: url }, (response) => {
      const chunks = [];
      response.on('data', (chunk) => chunks.push(chunk));
      response.on('end', () => {
        const body = Buffer.concat(chunks);
        mockRequests.push({ url, status: response.statusCode, bytes: body.length });
        if (response.statusCode !== 200) reject(new Error(`HTTP ${response.statusCode}`));
        else resolve(JSON.parse(body.toString()));
      });
    });
    request.on('error', reject);
  });
  mockPending.add(promise);
  promise.finally(() => mockPending.delete(promise));
  return promise;
}

jest.mock('../utils', () => ({
  getRestaurants: () => mockFetchJSON('/restaurants/menu'),
  getMenus: (id) => mockFetchJSON(`/restaurant/${id}/menu`),
  addItemToCart: jest.fn(),
}));
jest.mock('@ant-design/icons', () => ({ PlusOutlined: () => null }));
jest.mock('antd', () => {
  const React = require('react');
  const Select = ({ children, value, onSelect }) => (
    <select data-testid="restaurant" value={value} onChange={(event) => onSelect(Number(event.target.value))}>
      {children}
    </select>
  );
  Select.Option = ({ value, children }) => <option value={value}>{children}</option>;
  const List = ({ dataSource, renderItem }) => <div data-testid="menu-list">{dataSource.map((item) => <React.Fragment key={item.id}>{renderItem(item)}</React.Fragment>)}</div>;
  List.Item = ({ children }) => <div data-testid="menu-item">{children}</div>;
  return {
    Select, List,
    Button: ({ children, onClick }) => <button onClick={onClick}>{children}</button>,
    Card: ({ children, title, extra }) => <div><strong>{title}</strong>{extra}{children}</div>,
    Tooltip: ({ children }) => <span>{children}</span>,
    message: { error: (message) => { throw new Error(message); }, success: jest.fn() },
  };
});

async function settle() {
  await act(async () => { await Promise.all([...mockPending]); });
}

const benchmarkTest = process.env.ONLINEORDER_HTTP_BENCH === '1' ? test : test.skip;
benchmarkTest('measures the original and optimized ten-restaurant browsing flows with real HTTP responses', async () => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  const results = {};
  for (const [name, Component, port] of [['baseline', BaselineFoodList, 18080], ['optimized', FoodList, 18081]]) {
    mockPort = port;
    mockRequests = [];
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);
    await act(async () => { root.render(<Component />); });
    await settle();
    expect(container.querySelectorAll('option')).toHaveLength(100);
    for (let id = 1; id <= 10; id++) {
      await act(async () => {
        Simulate.change(container.querySelector('select'), { target: { value: String(id) } });
      });
      await settle();
      expect(container.querySelectorAll('[data-testid="menu-item"]')).toHaveLength(100);
      expect(container.textContent).toContain(`Menu item ${(id - 1) * 100 + 1}`);
      expect(container.textContent).toContain(`Menu item ${id * 100}`);
    }
    results[name] = { requests: mockRequests.length, bytes: mockRequests.reduce((sum, request) => sum + request.bytes, 0), responses: [...mockRequests] };
    await act(async () => root.unmount());
    container.remove();
  }
  expect(results.baseline.requests).toBe(11);
  expect(results.optimized.requests).toBe(1);
  expect(results.optimized.bytes).toBeLessThan(results.baseline.bytes);
  const output = path.resolve(process.cwd(), '../benchmarks/results/frontend-results.json');
  fs.writeFileSync(output, JSON.stringify({ scope: 'React components with substituted Ant Design presentation controls and real HTTP requests; JSON response body bytes, not compressed wire bytes', restaurants_browsed: 10, ...results }, null, 2));
  console.log('Frontend benchmark:', JSON.stringify(results));
}, 60000);
