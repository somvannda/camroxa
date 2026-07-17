import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import { StartupPage } from '@/features/startup/StartupPage'

describe('StartupPage', () => {
  it('renders the startup bootstrap surface', async () => {
    render(
      <MemoryRouter initialEntries={['/startup']}>
        <StartupPage />
      </MemoryRouter>,
    )

    expect(screen.getByText(/^loading$/i)).toBeInTheDocument()
    expect(await screen.findByText(/opening sign in/i)).toBeInTheDocument()
  })
})
