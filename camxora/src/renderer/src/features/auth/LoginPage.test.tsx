import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import { LoginPage } from '@/features/auth/LoginPage'

describe('LoginPage', () => {
  it('shows validation errors when required fields are invalid', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/auth/login']}>
        <LoginPage />
      </MemoryRouter>,
    )

    expect(screen.getByText(/welcome back/i)).toBeInTheDocument()
    expect(screen.getByText(/sign in to continue to your studio/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /forgot password/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create account on the web/i })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /^sign in$/i }))

    expect(await screen.findByText(/enter a valid email address/i)).toBeInTheDocument()
    expect(await screen.findByText(/password must be at least 8 characters/i)).toBeInTheDocument()
  })
})
