// Copyright 2026 Zyvor AI Labs · https://zyvor.dev
// SPDX-License-Identifier: Apache-2.0

import type {ReactNode} from 'react';
import {Redirect} from '@docusaurus/router';
import {ProductPage} from '../components/shared';

/** Legacy URL — MetalWolf was renamed to IronWolf. */
export default function MetalWolfLegacy(): ReactNode {
  return (
    <ProductPage title="MetalWolf" description="Redirecting to IronWolf.">
      <Redirect to="/ironwolf" />
    </ProductPage>
  );
}
