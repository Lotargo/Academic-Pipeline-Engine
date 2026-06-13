import { NextResponse } from 'next/server'

export async function POST(request: Request) {
  try {
    const body = await request.json()
    const backendUrl = process.env.BACKEND_API_URL || 'http://127.0.0.1:8000'
    
    const res = await fetch(`${backendUrl}/api/prompt/enhance`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })

    if (!res.ok) {
      const errorText = await res.text()
      return new NextResponse(errorText, { status: res.status })
    }

    const data = await res.json()
    return NextResponse.json(data)
  } catch (error: any) {
    console.error('Error in proxy route /api/prompt/enhance:', error)
    return new NextResponse(error.message || 'Internal Server Error', { status: 500 })
  }
}
