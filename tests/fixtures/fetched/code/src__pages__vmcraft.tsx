// Copyright 2026 Zyvor AI Labs · https://zyvor.dev
// SPDX-License-Identifier: Apache-2.0

import type {ReactNode} from 'react';
import {Redirect} from '@docusaurus/router';
import {ProductPage} from '../components/shared';

/** Legacy URL — VMCraft engine is part of hyper2kvm. */
export default function VMCraft(): ReactNode {
  return (
    <ProductPage title="VMCraft Engine" description="Redirecting to hyper2kvm.">
      <Redirect to="/hyper2kvm" />
    </ProductPage>
  );
}
