import { NextRequest, NextResponse } from "next/server"
import { updateRun } from "@/lib/repos/runs.repo"

export const runtime = "nodejs"

export async function POST(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    
    // Set hidden to true
    await updateRun(id, { hidden: true })
    
    return NextResponse.json({ 
      success: true,
      message: "Run hidden successfully" 
    })
  } catch (error) {
    return NextResponse.json(
      { 
        success: false,
        error: error instanceof Error ? error.message : "Failed to hide run" 
      },
      { status: 500 }
    )
  }
}

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    
    // Set hidden to false (unhide)
    await updateRun(id, { hidden: false })
    
    return NextResponse.json({ 
      success: true,
      message: "Run unhidden successfully" 
    })
  } catch (error) {
    return NextResponse.json(
      { 
        success: false,
        error: error instanceof Error ? error.message : "Failed to unhide run" 
      },
      { status: 500 }
    )
  }
}

