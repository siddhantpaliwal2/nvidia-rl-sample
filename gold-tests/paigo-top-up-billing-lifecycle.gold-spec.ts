import { plainToInstance } from 'class-transformer';
import { validate } from 'class-validator';

import { CreateOfferingDTO, ValidBillingCycles } from './dto/createOffering.dto.js';
import { OfferingPackageEntity, Offering } from './entities/offeringPackage.entity.js';
import { OfferingType } from './entities/OfferingType.js';
import { OfferingService } from './offering.service.js';
import { countBasedUnits, roundingEnum } from '../dimensions/dto/create-dimension.dto.js';
import { SupportedMeasurementFrequencies } from '../scheduler/dto/scheduler.dto.js';
import { FreeDimensionOnInvoice } from '../setting/dto/FreeDimensionOnInvoice.js';

// The historical change used a queue processor. A conforming implementation
// may instead process the trailing hour through the offering domain object.
// Resolve the optional processor at runtime so its filename is not mandatory.
let OfferingTopUpChecker: any;
try {
    OfferingTopUpChecker = require('../microservices/offeringTopUpHandler/offeringTopUp.service.js').OfferingTopUpChecker;
} catch (_error) {
    OfferingTopUpChecker = undefined;
}

const dimensionId = 'dimension-1';

function makeOffering({
    balance = '0',
    usageTotal = 0,
    customerId = 'customer-1',
    invoiceCreate = jest.fn(async () => ({ invoiceId: 'top-up-invoice' })),
    scheduler = { create: jest.fn(), remove: jest.fn() },
}: {
    balance?: string;
    usageTotal?: number;
    customerId?: string;
    invoiceCreate?: jest.Mock;
    scheduler?: { create: jest.Mock; remove?: jest.Mock };
} = {}) {
    let currentBalance = Number(balance);
    const creditCreate = jest.fn(async (request: any) => {
        currentBalance += Number(request.transactionAmount);
        return {};
    });
    const creditService = {
        create: creditCreate,
        findCreditBalance: jest.fn(async () => ({
            balance: currentBalance.toFixed(2),
            customerId,
            message: 'found',
        })),
    };
    const customerService = {
        creditService,
        findUsageForCustomer: jest.fn(async () => ({
            message: 'found',
            data: [
                {
                    dimensionId,
                    usage: [
                        {
                            startTime: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
                            endTime: new Date().toISOString(),
                            value: `${usageTotal}`,
                        },
                    ],
                },
            ],
        })),
    };
    const invoicesService = {
        create: invoiceCreate,
        queueInvoice: jest.fn(),
        consolidateInvoice: jest.fn(),
    };
    const offering = Offering.getInstance(
        {
            offeringId: 'offering-1',
            offeringName: 'Credits',
            offeringType: OfferingType.usageBased,
            billingCycle: ValidBillingCycles.topUp,
            topUpAmount: '100',
            topUpThreshold: '0.2',
            dimensions: [
                {
                    dimensionId,
                    dimensionName: 'Requests',
                    usageIncrement: '1',
                    consumptionUnit: { type: 'count', unit: countBasedUnits['count-based'] },
                    rounding: roundingEnum.ceiling,
                    consumptionPrice: '1',
                },
            ],
        } as any,
        customerId,
        'business-1',
        invoicesService as any,
        { freeDimensionOnInvoice: FreeDimensionOnInvoice.show } as any,
        scheduler as any,
        customerService as any,
        undefined,
        undefined,
        creditService as any,
    );
    return {
        offering,
        invoiceCreate,
        creditCreate,
        creditService,
        invoicesService,
        scheduler,
        balance: () => currentBalance.toFixed(2),
    };
}

describe('Top-up offering contract', () => {
    const dto = (extra: Record<string, unknown> = {}) =>
        plainToInstance(CreateOfferingDTO, {
            businessID: 'business-1',
            offeringName: 'Credits',
            offeringType: OfferingType.usageBased,
            billingCycle: ValidBillingCycles.topUp,
            topUpAmount: '100',
            ...extra,
        });

    const errorsFor = async (value: object, property: string) =>
        (await validate(value)).filter((error) => error.property === property);

    const expectBoundaryRejection = async (value: any, property: string) => {
        if ((await errorsFor(value, property)).length) return;
        const validator = (OfferingService as any).validateTopUpFields;
        expect(typeof validator).toBe('function');
        expect(() => validator(value)).toThrow();
    };

    it('accepts topUp for usage-based offerings and rejects it for subscriptions', async () => {
        await expect(errorsFor(dto(), 'billingCycle')).resolves.toEqual([]);
        const validator = (OfferingService as any).validateTopUpFields;
        if (validator) expect(() => validator(dto())).not.toThrow();
        await expectBoundaryRejection(
            dto({ offeringType: OfferingType.subscription }),
            'billingCycle',
        );
    });

    it('rejects top-up fields on a non-top-up billing cycle', async () => {
        await expectBoundaryRejection(
            dto({ billingCycle: ValidBillingCycles.monthly }),
            'topUpAmount',
        );
        await expectBoundaryRejection(
            dto({ billingCycle: ValidBillingCycles.monthly, topUpAmount: undefined, topUpThreshold: '0.3' }),
            'topUpThreshold',
        );
    });

    it('defaults the threshold and round-trips top-up fields through persistence', () => {
        const entity = new OfferingPackageEntity({
            ...dto(),
            offeringId: 'offering-1',
        } as any);
        expect(entity.topUpAmount).toBe('100');
        expect(entity.topUpThreshold).toBe('0.2');

        const point = { stringField: jest.fn(), tag: jest.fn() };
        const influx = { getPoint: jest.fn(() => point) };
        OfferingPackageEntity.transformer(entity, influx as any);
        expect(point.tag).toHaveBeenCalledWith('topUpAmount', '100');
        expect(point.tag).toHaveBeenCalledWith('topUpThreshold', '0.2');

        const restored = OfferingPackageEntity.dbModelToEntity({
            _value: 'Credits',
            businessID: 'business-1',
            offeringId: 'offering-1',
            offeringType: OfferingType.usageBased,
            billingCycle: ValidBillingCycles.topUp,
            subscriptionPrice: '0',
            topUpAmount: '100',
            topUpThreshold: '0.35',
        });
        expect(restored.topUpAmount).toBe('100');
        expect(restored.topUpThreshold).toBe('0.35');
    });

    it('creates one hourly offering-level scheduler with a stable id', async () => {
        const scheduler = { create: jest.fn() };
        const entity = new OfferingPackageEntity({ ...dto(), offeringId: 'offering-1' } as any);
        if (typeof (entity as any).createSchedules === 'function') {
            await (entity as any).createSchedules({ subject: 'subject-1', schedulerService: scheduler as any });
            expect(scheduler.create).toHaveBeenCalledTimes(1);
            expect(scheduler.create).toHaveBeenCalledWith(
                expect.objectContaining({
                    schedulerID: expect.any(String),
                    businessID: 'business-1',
                    rate: SupportedMeasurementFrequencies.everyHour,
                    scheduleParameters: expect.objectContaining({
                        offeringId: 'offering-1',
                        businessID: 'business-1',
                    }),
                }),
            );
            return;
        }

        const first = makeOffering({ scheduler, customerId: 'customer-1', balance: '100' }).offering;
        const second = makeOffering({ scheduler, customerId: 'customer-2', balance: '100' }).offering;
        await (first as any).registerBillingSchedule('subject-1');
        await (second as any).registerBillingSchedule('subject-1');
        expect(scheduler.create).toHaveBeenCalledTimes(2);
        const [firstSchedule, secondSchedule] = scheduler.create.mock.calls.map((call) => call[0]);
        expect(firstSchedule.rate).toBe(SupportedMeasurementFrequencies.everyHour);
        expect(secondSchedule.rate).toBe(SupportedMeasurementFrequencies.everyHour);
        expect(firstSchedule.schedulerID).toBe(secondSchedule.schedulerID);
    });

    const topUpOffering = (
        balance: string,
        invoiceCreate = jest.fn(async () => ({ invoiceId: 'top-up-invoice' })),
    ) =>
        makeOffering({ invoiceCreate, balance });

    it('does not top up a wallet at or above its threshold', async () => {
        const { offering, invoiceCreate } = topUpOffering('20.00');
        await offering.topUp({ customer: { customerId: 'customer-1', creditBalance: '20.00' } as any });
        expect(invoiceCreate).not.toHaveBeenCalled();
    });

    it('charges only the gap to the configured balance and stores payment as credit', async () => {
        const { offering, invoiceCreate } = topUpOffering('12.50');
        await offering.topUp({ customer: { customerId: 'customer-1', creditBalance: '12.50' } as any });
        expect(invoiceCreate).toHaveBeenCalledTimes(1);
        const input = invoiceCreate.mock.calls[0][0];
        expect(input.storePaymentAsCredit).toBe(true);
        expect(input.items.getLineItems()).toEqual([
            expect.objectContaining({ name: 'Credits - Top Up', quantity: 1, unitCost: 87.5 }),
        ]);
    });
});

describe('Hourly top-up usage processing', () => {
    const run = async (startingBalance: string, usageTotal: number) => {
        const topUp = jest.fn();
        const enrollment = { offering: { offeringId: 'offering-1' } };
        const customer = {
            customerId: 'customer-1',
            creditBalance: startingBalance,
            enrollments: [enrollment],
        };
        const creditCreate = jest.fn();
        const invoiceCreate = jest.fn();
        if (OfferingTopUpChecker) {
            const checker = new OfferingTopUpChecker(
                { findAll: jest.fn(async () => ({ data: [customer] })) } as any,
                {} as any,
                { findAll: jest.fn(async () => [{}]) } as any,
                {
                    generateLineItemsForEnrollment: jest.fn(async ({ lineItems }) => lineItems),
                    buildReadResponseInstanceFromEnrollment: jest.fn(() => ({
                        offering: { offeringId: 'offering-1', offeringName: 'Credits', topUp },
                    })),
                } as any,
                { create: creditCreate } as any,
                {
                    buildInvoice: jest.fn(async () => ({
                        customerId: 'customer-1',
                        totalAmountWithoutTax: usageTotal,
                    })),
                    create: invoiceCreate,
                } as any,
            );
            await checker.offeringTopUpChecker({
                data: {
                    scheduleParameters: { businessID: 'business-1', offeringId: 'offering-1' },
                    subject: 'subject-1',
                },
            } as any);
            return {
                balance: () => customer.creditBalance,
                creditCreate,
                invoiceCreate,
                topUp,
            };
        }

        const domain = makeOffering({ balance: startingBalance, usageTotal });
        const topUpSpy = jest.spyOn(domain.offering as any, 'topUp');
        await (domain.offering as any).processBilling(undefined, undefined, customer);
        return {
            balance: domain.balance,
            creditCreate: domain.creditCreate,
            invoiceCreate: domain.invoiceCreate,
            topUp: topUpSpy,
        };
    };

    const expectNoUsageInvoice = (invoiceCreate: jest.Mock) => {
        for (const [request] of invoiceCreate.mock.calls) {
            expect(request).toEqual(expect.objectContaining({ storePaymentAsCredit: true }));
        }
    };

    it('deducts the full hourly usage from wallet credit without issuing a usage invoice', async () => {
        const { balance, creditCreate, invoiceCreate, topUp } = await run('80.00', 30);
        expect(creditCreate.mock.calls[0][0]).toEqual(
            expect.objectContaining({
                customerId: 'customer-1',
                businessID: 'business-1',
                transactionAmount: '-30.00',
            }),
        );
        expect(balance()).toBe('50.00');
        expectNoUsageInvoice(invoiceCreate);
        expect(topUp).toHaveBeenCalled();
    });

    it('records usage beyond the current balance before evaluating the refill', async () => {
        const { balance, creditCreate, invoiceCreate, topUp } = await run('5.00', 12.5);
        expect(creditCreate.mock.calls[0][0]).toEqual(
            expect.objectContaining({ transactionAmount: '-12.50' }),
        );
        expect(balance()).toBe('-7.50');
        expectNoUsageInvoice(invoiceCreate);
        if (invoiceCreate.mock.calls.length) {
            const lineItems = invoiceCreate.mock.calls[0][0].items;
            const values = lineItems.getLineItems ? lineItems.getLineItems() : lineItems.lineItems;
            expect(values).toEqual([
                expect.objectContaining({ quantity: 1, unitCost: 107.5 }),
            ]);
        }
        expect(topUp).toHaveBeenCalled();
    });

    it('does no wallet mutation when the hour has no billable usage', async () => {
        const { balance, creditCreate, invoiceCreate, topUp } = await run('8.00', 0);
        expect(creditCreate).not.toHaveBeenCalled();
        expect(balance()).toBe('8.00');
        expectNoUsageInvoice(invoiceCreate);
        expect(topUp).toHaveBeenCalled();
    });
});
