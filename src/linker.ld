MEMORY
{
  FLASH (rx) : ORIGIN = 0x10000000, LENGTH = 2M
  RAM (rwx)  : ORIGIN = 0x38000000, LENGTH = 2M
}

/* Define the top of the stack at the end of RAM */
_estack = ORIGIN(RAM) + LENGTH(RAM);

ENTRY(Reset_Handler)

SECTIONS
{
  .text :
  {
    KEEP(*(.isr_vector))
    *(.text*)
    *(.rodata*)
    . = ALIGN(4);   /* Align the end of text/rodata */
    _etext = .;
  } > FLASH

  .data :
  {
    . = ALIGN(4);   /* Align the start of data */
    _sdata = .;
    *(.data*)
    . = ALIGN(4);   /* Align the end of data */
    _edata = .;
  } > RAM AT > FLASH

  .bss :
  {
    . = ALIGN(4);   /* Align the start of bss */
    _sbss = .;
    *(.bss*)
    *(COMMON)
    . = ALIGN(4);   /* Align the end of bss */
    _ebss = .;
  } > RAM
}