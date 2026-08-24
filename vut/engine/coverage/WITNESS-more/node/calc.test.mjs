import { test } from 'node:test';
import assert from 'node:assert';
import { double } from './calc.mjs';

test('double of positive', () => { assert.equal(double(3), 6); });
