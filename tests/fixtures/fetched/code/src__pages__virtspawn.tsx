// Copyright 2026 Zyvor AI Labs · https://zyvor.dev
// SPDX-License-Identifier: Apache-2.0

import type {ReactNode} from 'react';
import {Redirect} from '@docusaurus/router';
import {ProductPage} from '../components/shared';

/** Legacy product URL — VirtSpawn capabilities live in Machina. */
export default function VirtSpawnLegacy(): ReactNode {
  return (
    <ProductPage title="VirtSpawn" description="Redirecting to Machina.">
      <Redirect to="/machina" />
    </ProductPage>
  );
}
