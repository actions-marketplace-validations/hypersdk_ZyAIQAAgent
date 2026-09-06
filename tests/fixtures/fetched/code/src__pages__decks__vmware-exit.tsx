// Copyright 2026 Zyvor AI Labs · https://zyvor.dev
// SPDX-License-Identifier: Apache-2.0

import type {ReactNode} from 'react';
import {Redirect} from '@docusaurus/router';
import {ProductPage} from '../../components/shared';

export default function DecksVmwareExit(): ReactNode {
  return (
    <ProductPage title="VMware exit decks" description="Redirecting to VMware exit reading path.">
      <Redirect to="/vmware-exit?path=vmware-exit" />
    </ProductPage>
  );
}
