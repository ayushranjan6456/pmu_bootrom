extern unsigned int _estack;
extern unsigned int _etext, _sdata, _edata, _sbss, _ebss;

void Reset_Handler(void);
void Default_Handler(void) { while(1); }

/* Weak aliases for faults and interrupts */
__attribute__((weak, alias("Default_Handler"))) void NMI_Handler(void);
__attribute__((weak, alias("Default_Handler"))) void HardFault_Handler(void);

/* The interrupt vector table */
__attribute__((section(".isr_vector"), used))
void (*const g_pfnVectors[])(void) = {
    (void (*)(void))&_estack,
    Reset_Handler,
    NMI_Handler,
    HardFault_Handler
};

extern int main(void);

void Reset_Handler(void) {
    /* Copy initialized data (.data) from flash to RAM */
    unsigned int *src = &_etext;
    unsigned int *dst = &_sdata;
    while (dst < &_edata) {
        *dst++ = *src++;
    }
    
    /* Zero out the uninitialized data (.bss) in RAM */
    dst = &_sbss;
    while (dst < &_ebss) {
        *dst++ = 0;
    }
    
    /* Jump to our main application */
    main();
    
    /* Trap if main returns */
    while (1);
}