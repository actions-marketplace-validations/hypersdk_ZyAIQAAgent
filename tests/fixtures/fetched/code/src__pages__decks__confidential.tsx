// Copyright 2026 Zyvor AI Labs · https://zyvor.dev
// SPDX-License-Identifier: Apache-2.0

import type {ReactNode} from 'react';
import {DeckPathLandingPage} from '../../components/DeckPathLandingPage';

export default function DecksConfidential(): ReactNode {
  return <DeckPathLandingPage pathId="confidential" contactIntent="compliance" />;
}
